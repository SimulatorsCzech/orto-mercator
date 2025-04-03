
"""
Plugin: Konečný ořez území
Autor: [Vaše jméno]
Popis:
  Tento plugin provádí konečný ořez geotiffových dlaždic podle tvaru vybraného regionu.
  – Vstupní adresář s geotiff dlaždicemi se načítá z global_context["tiles_output_dir"].
  – Shapefile regionu se načítá z global_context["selected_shapefile"].
  – Shapefile je přeprojektován do EPSG:4326; volitelně se aplikuje buffer.
  – Na každé dlaždici se vytvoří maska (s feather efektem) a tato maska se použije jako alfa kanál.
  – Výstupní GeoTIFF s průhledností mimo region se uloží do zvoleného výstupního adresáře.
  
Bibliotéky: GDAL, OGR, OpenCV, numpy, PySide6

Poznámka:
  Je nutné, aby global_context obsahoval klíče "selected_shapefile", "selected_region",
  "tiles_output_dir" a "final_tiles_dir".
"""

import os
import glob
import cv2
import numpy as np
from osgeo import gdal, ogr, osr
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QLineEdit, QSlider, QPushButton,
                               QFileDialog, QHBoxLayout, QMessageBox, QProgressBar, QGroupBox, QComboBox,
                               QCheckBox)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QPixmap, QImage

from plugins.plugin_base import PluginBase
from plugins.global_context import global_context
from plugins.signal_manager import signal_manager

def sanitize_filename(name: str) -> str:
    """
    Odstraní diakritiku, interpunkci, speciální znaky a mezery z názvu.
    Vrací řetězec obsahující pouze alfanumerické znaky, podtržítka, pomlčky a tečky.
    Tuto funkci lze použít pro názvy souborů i složek.
    """
    normalized = unicodedata.normalize('NFKD', name).encode('ASCII', 'ignore').decode('ASCII')
    sanitized = re.sub(r'[^A-Za-z0-9_.-]', '', normalized)
    return sanitized

def next_power_of_two(n: int) -> int:
    """Vrací nejmenší mocninu 2, která je větší nebo rovna n."""
    if n <= 0:
        return 1
    return 2 ** int(np.ceil(np.log2(n)))

class FinalRegionCropWorker(QThread):
    progress_updated = Signal(int, int)  # (current processed tile, total tiles)
    process_finished = Signal(str)       # výstupní adresář
    process_error = Signal(str)

    def __init__(self, input_dir: str, output_dir: str, feather: int, source_srs: str, buffer_value: float, skip_transparent: bool = False):
        super().__init__()
        self.input_dir = input_dir      # Adresář s geotiff dlaždicemi (z global_context)
        self.output_dir = output_dir    # Výstupní adresář pro finální dlaždice
        self.feather = feather          # Feather efekt (v pixelech)
        self.source_srs = source_srs    # Zdrojová SRS původního shapefile
        self.buffer_value = buffer_value# Buffer v metrech
        self.skip_transparent = skip_transparent  # Zda přeskočit plně průhledné dlaždice
        self._is_running = True

    def stop(self):
        self._is_running = False
        print("[KONEČNÝ OŘEZ UŽETÍ] Zastavuji worker.")

    def reproject_shapefile_to_wgs84(self, shapefile_path: str, tmp_path: str) -> str:
        try:
            # V této úpravě předpokládáme, že vkládaný shapefile je ve WebMercator, proto
            # vždy reprojektujeme ze zdrojové SRS EPSG:3857 do cílové EPSG:4326.
            cmd = f'ogr2ogr -s_srs EPSG:3857 -t_srs EPSG:4326 "{tmp_path}" "{shapefile_path}"'
            print(f"[KONEČNÝ OŘEZ UŽETÍ] Reprojekce shapefile: Spouštím příkaz: {cmd}")
            result = os.system(cmd)
            if result != 0:
                raise Exception("Chyba při reprojekci shapefile.")
            print(f"[KONEČNÝ OŘEZ UŽETÍ] Shapefile byl přeprojektován do EPSG:4326 a uložen do: {tmp_path}")
            return tmp_path
        except Exception as e:
            print(f"[KONEČNÝ OŘEZ UŽETÍ] Chyba v reprojekci shapefile: {e}")
            raise e

    def rasterize_polygon(self, polygon_geom, tile_gt, tile_xsize, tile_ysize) -> np.ndarray:
        print("[KONEČNÝ OŘEZ UŽETÍ] Rasterizuji polygon na dlaždici se rozměry:", tile_xsize, "x", tile_ysize)
        mem_driver = gdal.GetDriverByName("MEM")
        target_ds = mem_driver.Create("", tile_xsize, tile_ysize, 1, gdal.GDT_Byte)
        target_ds.SetGeoTransform(tile_gt)
        srs = osr.SpatialReference()
        srs.ImportFromEPSG(4326)
        target_ds.SetProjection(srs.ExportToWkt())
        mem_vector_driver = ogr.GetDriverByName("Memory")
        mem_vector_ds = mem_vector_driver.CreateDataSource("memData")
        mem_layer = mem_vector_ds.CreateLayer("layer", srs, ogr.wkbPolygon)
        feature_def = mem_layer.GetLayerDefn()
        feature = ogr.Feature(feature_def)
        feature.SetGeometry(polygon_geom)
        mem_layer.CreateFeature(feature)
        feature = None
        gdal.RasterizeLayer(target_ds, [1], mem_layer, burn_values=[255])
        band = target_ds.GetRasterBand(1)
        mask = band.ReadAsArray()
        mem_vector_ds = None
        target_ds = None
        return mask

    def apply_feather(self, mask: np.ndarray) -> np.ndarray:
        ksize = 2 * self.feather + 1
        print(f"[KONEČNÝ OŘEZ UŽETÍ] Aplikuji feather efekt s kernel size {ksize}.")
        blurred = cv2.GaussianBlur(mask, (ksize, ksize), 0)
        return blurred

    def process_tile(self, tile_file: str, polygon_geom) -> str:
        print(f"[KONEČNÝ OŘEZ UŽETÍ] Zpracovávám dlaždici: {tile_file}")
        ds = gdal.Open(tile_file, gdal.GA_ReadOnly)
        if ds is None:
            raise Exception(f"Nelze otevřít dlaždici: {tile_file}")
        tile_gt = ds.GetGeoTransform()
        tile_xsize = ds.RasterXSize
        tile_ysize = ds.RasterYSize
        margin = self.feather  # margin rozšíření oblasti pro plynulé přechody
        new_tile_xsize = tile_xsize + 2 * margin
        new_tile_ysize = tile_ysize + 2 * margin
        new_gt = (tile_gt[0] - margin * tile_gt[1],
                  tile_gt[1],
                  tile_gt[2],
                  tile_gt[3] - margin * tile_gt[5],
                  tile_gt[4],
                  tile_gt[5])
        mask_expanded = self.rasterize_polygon(polygon_geom, new_gt, new_tile_xsize, new_tile_ysize)
        feathered_mask_expanded = self.apply_feather(mask_expanded)
        # Oříznutí masky na původní velikost dlaždice
        feathered_mask = feathered_mask_expanded[margin:margin+tile_ysize, margin:margin+tile_xsize]
        tile_array = ds.ReadAsArray()
        ds = None
        if tile_array is None:
            raise Exception(f"Chyba při čtení dat z dlaždice: {tile_file}")
        print(f"[DEBUG] Původní tvar dlaždice: {tile_array.shape}, dtype: {tile_array.dtype}")
        if tile_array.ndim == 3:
            tile_array = np.transpose(tile_array, (1, 2, 0))
            print(f"[DEBUG] Po transpose: {tile_array.shape}, dtype: {tile_array.dtype}")
        else:
            tile_array = tile_array[..., np.newaxis]
            print(f"[DEBUG] Jednovrstvý obraz převeden na: {tile_array.shape}, dtype: {tile_array.dtype}")
        if tile_array.shape[2] >= 3:
            output_array = np.dstack((tile_array[:, :, :3], feathered_mask))
        else:
            output_array = np.dstack((tile_array, tile_array, tile_array, feathered_mask))
        print(f"[DEBUG] Výstupní pole před padováním: {output_array.shape}, dtype: {output_array.dtype}")
        
        # Padování obrazu na rozměry, které jsou mocninou 2
        h, w, c = output_array.shape
        new_w = next_power_of_two(w)
        new_h = next_power_of_two(h)
        if new_w != w or new_h != h:
            print(f"[KONEČNÝ OŘEZ UŽETÍ] Padování dlaždice z {w}x{h} na {new_w}x{new_h}.")
            padded_image = np.zeros((new_h, new_w, c), dtype=output_array.dtype)
            # Zkopírujeme původní obraz do levého horního rohu
            padded_image[:h, :w, :] = output_array
            output_array = padded_image
        print(f"[DEBUG] Výstupní pole po padování: {output_array.shape}, dtype: {output_array.dtype}")
        
        # Kontrola transparentnosti: pokud je volba aktivní a alfa kanál je kompletně nulový, dlaždice se přeskočí.
        alpha_channel = output_array[:, :, -1]
        if self.skip_transparent and np.all(alpha_channel == 0):
            print("[KONEČNÝ OŘEZ UŽETÍ] Dlaždice je kompletně průhledná, přeskočím její uložení.")
            return "skipped"
            
        base_name = os.path.basename(tile_file)
        sanitized_name = sanitize_filename(base_name)
        output_file = os.path.join(self.output_dir, sanitized_name)
        print(f"[KONEČNÝ OŘEZ UŽETÍ] Ukládám zpracovanou dlaždici jako: {output_file}")
        driver = gdal.GetDriverByName("GTiff")
        creation_options = ["TILED=YES", "COMPRESS=NONE"]
        # Vytvoříme dataset s novým rozměrem
        out_ds = driver.Create(output_file, output_array.shape[1], output_array.shape[0], output_array.shape[2], gdal.GDT_Byte, options=creation_options)
        if not out_ds:
            raise Exception("Nelze vytvořit výstupní dataset.")
        out_ds.SetGeoTransform(tile_gt)
        srs = osr.SpatialReference()
        srs.ImportFromEPSG(4326)
        out_ds.SetProjection(srs.ExportToWkt())
        for i in range(output_array.shape[2]):
            band = out_ds.GetRasterBand(i+1)
            band.WriteArray(output_array[:, :, i])
            band.FlushCache()
        out_ds = None
        print(f"[KONEČNÝ OŘEZ UŽETÍ] Dlaždice zpracována: {tile_file} → {output_file}")
        return output_file

    def run(self):
        try:
            print(f"[KONEČNÝ OŘEZ UŽETÍ] Vstupní adresář: '{self.input_dir}'")
            print(f"[KONEČNÝ OŘEZ UŽETÍ] Výstupní adresář: '{self.output_dir}'")
            tiles = glob.glob(os.path.join(self.input_dir, "*.tif"))
            total_tiles = len(tiles)
            print(f"[KONEČNÝ OŘEZ UŽETÍ] Nalezeno {total_tiles} dlaždic.")
            if total_tiles == 0:
                raise Exception("Nebyl nalezen žádný geotiff ve vstupním adresáři.")
            shapefile_path = global_context.get("selected_shapefile")
            if not shapefile_path:
                raise Exception("global_context neobsahuje 'selected_shapefile'.")
            print(f"[KONEČNÝ OŘEZ UŽETÍ] Používám shapefile: '{shapefile_path}'")
            # Předpokládáme, že vkládaný shapefile je již v CRS WebMercator, takže reprojekce proběhne ze EPSG:3857 do EPSG:4326
            tmp_reproj_shp = os.path.join(self.output_dir, "temp_reproj.shp")
            print(f"[KONEČNÝ OŘEZ UŽETÍ] Dočasný přeprojektovaný shapefile bude uložen do: '{tmp_reproj_shp}'")
            self.reproject_shapefile_to_wgs84(shapefile_path, tmp_reproj_shp)
            shp_ds = ogr.Open(tmp_reproj_shp)
            if shp_ds is None:
                raise Exception(f"Nelze otevřít přeprojektovaný shapefile: '{tmp_reproj_shp}'")
            layer = shp_ds.GetLayer()
            feat = layer.GetNextFeature()
            if feat is None:
                raise Exception("Přeprojektovaný shapefile neobsahuje geometrii.")
            polygon_geom = feat.GetGeometryRef().Clone()
            shp_ds = None
            if self.buffer_value > 0:
                print(f"[KONEČNÝ OŘEZ UŽETÍ] Aplikuji buffer o hodnotě: {self.buffer_value} m")
                polygon_geom = polygon_geom.Buffer(self.buffer_value)
            os.makedirs(self.output_dir, exist_ok=True)
            processed = 0

            # Paralelizace zpracování dlaždic
            with ThreadPoolExecutor(max_workers=os.cpu_count()) as executor:
                future_to_tile = {executor.submit(self.process_tile, tile, polygon_geom): tile for tile in tiles}
                for future in as_completed(future_to_tile):
                    if not self._is_running:
                        print("[KONEČNÝ OŘEZ UŽETÍ] Proces byl zastaven.")
                        break
                    future.result()
                    processed += 1
                    self.progress_updated.emit(processed, total_tiles)
                    print(f"[KONEČNÝ OŘEZ UŽETÍ] Zpracováno {processed}/{total_tiles} dlaždic.")

            print(f"[KONEČNÝ OŘEZ UŽETÍ] Zpracování dokončeno. Výstupní složka: '{self.output_dir}'")
            self.process_finished.emit(self.output_dir)
        except Exception as e:
            print(f"[KONEČNÝ OŘEZ UŽETÍ] Chyba v run(): {e}")
            self.process_error.emit(str(e))

class FinalRegionCropPlugin(PluginBase):
    def __init__(self):
        self.config = {
            "output_dir": global_context.get("final_tiles_dir", os.path.join("data", "final_tiles"))
        }
        self.input_dir_edit = None
        self.output_dir_edit = None
        self.feather_slider = None
        self.feather_lineedit = None
        self.source_srs_combo = None
        self.buffer_lineedit = None
        self.skip_transparent_checkbox = None
        self.process_button = None
        self.progress_bar = None
        self.status_label = None
        self.crop_worker = None

    def name(self) -> str:
        return "Konečný ořez území"

    def description(self) -> str:
        return ("Plugin provádí konečný ořez geotiffových dlaždic podle tvaru vybraného shapefile. "
                "Shapefile je přeprojektován do EPSG:4326, s volitelným bufferem a feather efektem. "
                "Výstupem je GeoTIFF s průhledností mimo region.")

    def get_default_config(self) -> dict:
        return self.config

    def update_config(self, new_config: dict):
        self.config.update(new_config)

    def select_output_dir(self):
        directory = QFileDialog.getExistingDirectory(None, "Vyberte adresář pro finální dlaždice", self.output_dir_edit.text())
        if directory:
            self.output_dir_edit.setText(directory)
            print(f"[KONEČNÝ OŘEZ UŽETÍ] Nový výstupní adresář nastaven: '{directory}'")

    def on_process_button_clicked(self):
        input_dir = global_context.get("tiles_output_dir", os.path.join("data", "geotiff_tiles"))
        print(f"[KONEČNÝ OŘEZ UŽETÍ] Aktualizuji vstupní adresář z global_context: '{input_dir}'")
        self.input_dir_edit.setText(input_dir)
        output_dir = self.output_dir_edit.text()
        print(f"[KONEČNÝ OŘEZ UŽETÍ] Používám výstupní adresář: '{output_dir}'")
        try:
            feather = int(self.feather_lineedit.text())
        except Exception:
            feather = self.feather_slider.value()
        try:
            buffer_value = float(self.buffer_lineedit.text())
        except Exception:
            buffer_value = 0.0
        # I když se v UI zobrazuje volba SRS, nyní expectujeme, že shapefile je ve WebMercator,
        # takže výchozí hodnota by měla být EPSG:3857.
        source_srs = self.source_srs_combo.currentText()
        skip_transparent = self.skip_transparent_checkbox.isChecked()
        print(f"[KONEČNÝ OŘEZ UŽETÍ] Parametry: feather={feather}, buffer={buffer_value}, source_srs='{source_srs}', skip_transparent={skip_transparent}")
        self.crop_worker = FinalRegionCropWorker(input_dir, output_dir, feather, source_srs, buffer_value, skip_transparent)
        self.crop_worker.progress_updated.connect(lambda current, total: self.progress_bar.setValue(int((current/total)*100)))
        self.crop_worker.process_finished.connect(self.on_process_finished)
        self.crop_worker.process_error.connect(self.on_process_error)
        self.crop_worker.start()
        self.process_button.setEnabled(False)
        self.status_label.setText("Zahajuji konečný ořez dlaždic ...")

    def on_process_finished(self, out_dir: str):
        self.status_label.setText(f"Konečný ořez dokončen. Výstup v: {out_dir}")
        self.process_button.setEnabled(True)
        print(f"[KONEČNÝ OŘEZ UŽETÍ] Proces dokončen. Výstupní složka: '{out_dir}'")

    def on_process_error(self, err: str):
        self.status_label.setText(f"Chyba při ořezu: {err}")
        self.process_button.setEnabled(True)
        print(f"[KONEČNÝ OŘEZ UŽETÍ] Chyba při ořezu: {err}")

    def setup_ui(self, parent: QWidget) -> QWidget:
        widget = QWidget(parent)
        layout = QVBoxLayout(widget)
        title = QLabel("<h2>Konečný ořez území</h2>", widget)
        layout.addWidget(title)
        info = QLabel("Plugin ořeže geotiffy podle tvaru vybraného shapefile. Vstupní adresář se čerpá z global_context a aktualizuje před spuštěním procesu.\nNastavte zdrojovou SRS, buffer a feather efekt (přepočet vychází ze skutečného rozlišení dlaždic).\nVýstupní textury budou automaticky doplněny na rozměry, které jsou mocninou dvou.", widget)
        info.setWordWrap(True)
        layout.addWidget(info)
        in_layout = QHBoxLayout()
        in_label = QLabel("Vstupní adresář:", widget)
        default_input = global_context.get("tiles_output_dir", os.path.join("data", "geotiff_tiles"))
        self.input_dir_edit = QLineEdit(default_input, widget)
        self.input_dir_edit.setReadOnly(True)
        in_layout.addWidget(in_label)
        in_layout.addWidget(self.input_dir_edit)
        layout.addLayout(in_layout)
        out_layout = QHBoxLayout()
        out_label = QLabel("Výstupní adresář:", widget)
        self.output_dir_edit = QLineEdit(self.config["output_dir"], widget)
        out_button = QPushButton("...", widget)
        out_button.clicked.connect(self.select_output_dir)
        out_layout.addWidget(out_label)
        out_layout.addWidget(self.output_dir_edit)
        out_layout.addWidget(out_button)
        layout.addLayout(out_layout)
        srs_buffer_group = QGroupBox("Nastavení shapefile", widget)
        srs_buffer_layout = QHBoxLayout()
        srs_label = QLabel("Původní SRS:", widget)
        self.source_srs_combo = QComboBox(widget)
        # Upraveno: výchozí hodnota nastavena na EPSG:3857
        self.source_srs_combo.addItems(["EPSG:3857", "EPSG:4326", "EPSG:5514"])
        self.source_srs_combo.setCurrentText("EPSG:3857")
        buffer_label = QLabel("Buffer (m):", widget)
        self.buffer_lineedit = QLineEdit("0", widget)
        self.buffer_lineedit.setFixedWidth(50)
        srs_buffer_layout.addWidget(srs_label)
        srs_buffer_layout.addWidget(self.source_srs_combo)
        srs_buffer_layout.addWidget(buffer_label)
        srs_buffer_layout.addWidget(self.buffer_lineedit)
        srs_buffer_group.setLayout(srs_buffer_layout)
        layout.addWidget(srs_buffer_group)
        def get_pixel_resolution():
            """
            Vrátí průměrnou velikost pixelu (v metrech) podle hodnoty uložené v global_context["ortofoto_resolution"].
            Pokud tato hodnota není nastavena, vrátí se fallback 0.5 m/px.
            """
            res = global_context.get("ortofoto_resolution")
            if res is not None:
                try:
                    calculated_res = float(res)
                    print(f"[KONEČNÝ OŘEZ UŽETÍ] Používám hodnotu ortofoto_resolution z global_context: {calculated_res} m/px")
                    return calculated_res
                except Exception as e:
                    print(f"[KONEČNÝ OŘEZ UŽETÍ] Chyba při převodu ortofoto_resolution: {e}")
            print("[KONEČNÝ OŘEZ UŽETÍ] Hodnota ortofoto_resolution není nastavena, používám fallback 0.5 m/px.")
            return 0.5
        feather_group = QGroupBox("Nastavení feather efektu – šířka (v pixelech)", widget)
        feather_layout = QHBoxLayout()
        self.feather_slider = QSlider(Qt.Horizontal, widget)
        self.feather_slider.setRange(0, 1000)
        self.feather_slider.setValue(30)
        self.feather_lineedit = QLineEdit("30", widget)
        self.feather_lineedit.setFixedWidth(50)
        self.feather_meters_label = QLabel("", widget)
        def update_feather_value(val):
            self.feather_lineedit.setText(str(val))
            pixel_size = get_pixel_resolution()
            meters = val * pixel_size
            self.feather_meters_label.setText(f"{val} px = {meters:.2f} m")
        self.feather_slider.valueChanged.connect(update_feather_value)
        self.feather_lineedit.editingFinished.connect(lambda: self.feather_slider.setValue(int(self.feather_lineedit.text())))
        update_feather_value(self.feather_slider.value())
        feather_layout.addWidget(self.feather_slider)
        feather_layout.addWidget(self.feather_lineedit)
        feather_layout.addWidget(self.feather_meters_label)
        feather_group.setLayout(feather_layout)
        layout.addWidget(feather_group)
        
        # Přidání checkboxu pro přeskočení plně průhledných dlaždic
        self.skip_transparent_checkbox = QCheckBox("Přeskočit plně průhledné dlaždice", widget)
        self.skip_transparent_checkbox.setToolTip("Pokud je zaškrtnuto, dlaždice, které jsou po ořezu zcela průhledné, nebudou uloženy")
        layout.addWidget(self.skip_transparent_checkbox)
        
        self.process_button = QPushButton("Spustit konečný ořez", widget)
        self.process_button.clicked.connect(self.on_process_button_clicked)
        layout.addWidget(self.process_button)
        self.progress_bar = QProgressBar(widget)
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)
        self.status_label = QLabel("Připraveno ke konečnému ořezu.", widget)
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        layout.addStretch()
        return widget

    def execute(self, data):
        pass

if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication
    import sys
    app = QApplication(sys.argv)
    test_window = QWidget()
    test_layout = QVBoxLayout(test_window)
    plugin = FinalRegionCropPlugin()
    ui = plugin.setup_ui(test_window)
    test_layout.addWidget(ui)
    test_window.show()
    sys.exit(app.exec())
# KONEC SOUBORU
