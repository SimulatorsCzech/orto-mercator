
import os
import glob
import datetime
import math
import re
import unicodedata
from subprocess import CalledProcessError
from concurrent.futures import ThreadPoolExecutor, as_completed

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QFileDialog, QMessageBox, QProgressBar, QGroupBox, QComboBox
)
from PySide6.QtCore import Qt

from plugins.plugin_base import PluginBase
from plugins.global_context import global_context
from plugins.signal_manager import signal_manager

def sanitize_filename(name: str) -> str:
    normalized = unicodedata.normalize('NFKD', name).encode('ASCII', 'ignore').decode('ASCII')
    return re.sub(r'[^A-Za-z0-9_.-]', '', normalized)

class DsfPrepPlugin(PluginBase):
    def __init__(self):
        self.config = {
            "input_dir": global_context.get("final_tiles_dir", os.path.join("data", "final_tiles")),
            "output_dir": os.path.join("data", "dsf_prep"),
            "layer_group_beaches": "1"  # Nová konfigurace – výchozí hodnota 1
        }
        self.input_dir_edit = None
        self.output_dir_edit = None
        self.planet_combo = None
        self.dds_conversion_combo = None
        self.process_button = None
        self.progress_bar = None
        self.status_label = None
        # Nová pole pro zadání cílového DSF čtverce (levý dolní roh)
        self.target_lat_edit = None  # float, např. 50
        self.target_lon_edit = None  # float, např. 10
        # Nové pole pro možnost přepsání hodnoty LAYER_GROUP beaches
        self.layer_group_edit = None

    def name(self) -> str:
        return "DSF Příprava Inputu z konečných ořezaných geotiffů"

    def description(self) -> str:
        return (
            "Plugin načte konečné ořezané geotiffy a vytvoří DSF vstupní soubor a odpovídající .pol soubory. "
            "Na základě metadat se přesně spočítají LOAD_CENTER, SCALE (v metrech) a hranice dlaždice. "
            "Geotiffy se seskupí do 1°×1° oblastí, přičemž DSF soubor obsahuje pevnou hlavičku a pro každou dlaždici "
            "je generován polygonový blok s přesnými souřadnicemi, jak vyžaduje X-Plane. Pokud zadáte cílový čtverec, "
            "zpracují se pouze dlaždice, jejichž bounding box zasahuje do tohoto čtverce; ostatní se odstraní. "
            "V DSF souborech však dlaždice zůstávají zapsány standardně – jejich polygonové body jsou oříznuty přesně podle hranice čtverce. "
            "Odkaz na texturu se zapisuje pomocí řádku POLYGON_DEF, který vypadá například: "
            "\"POLYGON_DEF textury/N50E016_r0000_c0000.pol\". Plugin vytváří mapping mezi .pol soubory a jejich indexy, "
            "které jsou pak použity v BEGIN_POLYGON příkazech pro správné přiřazení textur."
        )

    def get_default_config(self) -> dict:
        return self.config

    def update_config(self, new_config: dict):
        self.config.update(new_config)

    def select_input_dir(self):
        directory = QFileDialog.getExistingDirectory(None, "Vyberte vstupní adresář s konečnými geotiffy", self.input_dir_edit.text())
        if directory:
            self.input_dir_edit.setText(directory)
            self.config["input_dir"] = directory
            print(f"[DSF PREP] Vstupní adresář nastaven: {directory}")

    def select_output_dir(self):
        directory = QFileDialog.getExistingDirectory(None, "Vyberte výstupní adresář pro DSF a .pol soubory", self.output_dir_edit.text())
        if directory:
            self.output_dir_edit.setText(directory)
            self.config["output_dir"] = directory
            print(f"[DSF PREP] Výstupní adresář nastaven: {directory}")

    def convert_geotiff_to_dds(self, geotiff_path: str, dds_path: str, dds_format: str) -> None:
        try:
            from osgeo import gdal
            options = gdal.TranslateOptions(format="DDS", creationOptions=[f"FORMAT={dds_format}"])
            result = gdal.Translate(dds_path, geotiff_path, options=options)
            if result is None:
                print(f"[DSF PREP] Chyba při převodu {geotiff_path} do DDS.")
            else:
                print(f"[DSF PREP] Úspěšně převeden {geotiff_path} do {dds_path} s formátem {dds_format}")
        except Exception as e:
            print(f"[DSF PREP] Výjimka při převodu {geotiff_path} do DDS: {e}")

    def create_pol_file(self, geotiff_path: str, output_dir: str) -> str:
        base = os.path.basename(geotiff_path)
        name_no_ext, ext = os.path.splitext(base)
        base_texture = name_no_ext + ".dds"
        textures_dir = os.path.join(output_dir, "Textury")
        os.makedirs(textures_dir, exist_ok=True)
        dds_path = os.path.join(textures_dir, base_texture)
        pol_filename = sanitize_filename(name_no_ext) + ".pol"
        pol_path = os.path.join(textures_dir, pol_filename)
        if os.path.exists(pol_path):
            print(f"[DSF PREP] .pol soubor již existuje: {pol_path}")
            return pol_path
        try:
            from osgeo import gdal
            ds = gdal.Open(geotiff_path, gdal.GA_ReadOnly)
            if ds:
                gt = ds.GetGeoTransform()
                width = ds.RasterXSize
                height = ds.RasterYSize
                center_x = gt[0] + (width / 2) * gt[1]
                center_y = gt[3] + (height / 2) * gt[5]
                center_lat_rad = center_y * math.pi / 180.0
                scale_x = width * abs(gt[1]) * 111320 * math.cos(center_lat_rad)
                scale_y = height * abs(gt[5]) * 111320
                terrain_size = math.sqrt(scale_x**2 + scale_y**2)
                texture_resolution = max(width, height)
                ds = None
            else:
                center_x, center_y, scale_x, scale_y = 0.0, 0.0, 0.0, 0.0
                terrain_size = 0.0
                texture_resolution = 0
        except Exception as e:
            print(f"[DSF PREP] Chyba při čtení metadat {geotiff_path}: {e}")
            center_x, center_y, scale_x, scale_y = 0.0, 0.0, 0.0, 0.0
            terrain_size = 0.0
            texture_resolution = 0

        with open(pol_path, "w", encoding="utf-8") as f:
            f.write("A\n")
            f.write("850\n")
            f.write("DRAPED_POLYGON\n")
            f.write("\n")
            f.write("# Created by SimulatorsCzech orl_cz\n")
            f.write(f"TEXTURE_NOWRAP {base_texture}\n")
            f.write(f"LOAD_CENTER {center_y:.9f} {center_x:.9f} {terrain_size:.1f} {texture_resolution}\n")
            f.write(f"SCALE {scale_x:.9f} {scale_y:.9f}\n")
            # Zapíšeme pouze jeden řádek s hodnotou LAYER_GROUP beaches převzatou z GUI
            f.write(f"LAYER_GROUP beaches {self.layer_group_edit.text()}\n")
        print(f"[DSF PREP] Vytvořen .pol soubor: {pol_path}")
        return pol_path

    def compute_tile_bounds(self, geotiff_path: str):
        try:
            from osgeo import gdal
            ds = gdal.Open(geotiff_path, gdal.GA_ReadOnly)
            if ds:
                gt = ds.GetGeoTransform()
                width = ds.RasterXSize
                height = ds.RasterYSize
                ds = None
                ulx = gt[0]
                uly = gt[3]
                east = ulx + width * gt[1]
                south = uly + height * gt[5]
                if south > uly:
                    south, uly = uly, south
                return (ulx, south, east, uly)
        except Exception as e:
            print(f"[DSF PREP] Chyba při výpočtu hranic {geotiff_path}: {e}")
        return (0.0, 0.0, 0.0, 0.0)

    def tile_is_transparent(self, geotiff_path: str) -> bool:
        try:
            from osgeo import gdal
            ds = gdal.Open(geotiff_path, gdal.GA_ReadOnly)
            if ds is None:
                return True
            if ds.RasterCount >= 4:
                band = ds.GetRasterBand(ds.RasterCount)
                arr = band.ReadAsArray()
                ds = None
                if arr is not None and (arr == 0).all():
                    return True
            ds = None
        except Exception as e:
            print(f"[DSF PREP] Chyba při kontrole transparentnosti {geotiff_path}: {e}")
        return False

    def run_conversion(self):
        input_dir = self.input_dir_edit.text()
        output_dir = self.output_dir_edit.text()
        if not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
        geotiff_files = glob.glob(os.path.join(input_dir, "*.tif"))
        if not geotiff_files:
            QMessageBox.critical(None, "Chyba", "Nebyly nalezeny žádné .tif soubory.")
            return

        filtered_files = []
        for tif_file in geotiff_files:
            if self.tile_is_transparent(tif_file):
                try:
                    os.remove(tif_file)
                    print(f"[DSF PREP] Odstraněn průhledný tif: {tif_file}")
                except Exception as ex:
                    print(f"[DSF PREP] Nelze smazat transparentní {tif_file}: {ex}")
            else:
                filtered_files.append(tif_file)
        geotiff_files = filtered_files
        if not geotiff_files:
            QMessageBox.information(None, "Informace", "Všechny dlaždice jsou průhledné nebo nebyly nalezeny žádné platné dlaždice.")
            return

        target_square = None
        if self.target_lat_edit.text().strip() and self.target_lon_edit.text().strip():
            try:
                target_lat = float(self.target_lat_edit.text().strip())
                target_lon = float(self.target_lon_edit.text().strip())
                target_square = {
                    "west": target_lon,
                    "east": target_lon + 1,
                    "south": target_lat,
                    "north": target_lat + 1
                }
                print(f"[DSF PREP] Cílový DSF čtverec: {target_square}")
            except Exception as e:
                print(f"[DSF PREP] Chyba při čtení cílového čtverce: {e}")
                target_square = None

        if target_square is not None:
            filtered_files = []
            for tif_file in geotiff_files:
                bounds = self.compute_tile_bounds(tif_file)
                tile_ulx, tile_s, tile_e, tile_n = bounds
                inter_w = max(tile_ulx, target_square["west"])
                inter_e = min(tile_e, target_square["east"])
                inter_s = max(tile_s, target_square["south"])
                inter_n = min(tile_n, target_square["north"])
                if inter_w < inter_e and inter_s < inter_n:
                    filtered_files.append(tif_file)
                else:
                    try:
                        os.remove(tif_file)
                        print(f"[DSF PREP] Odstraněn tif mimo cílový čtverec: {tif_file}")
                    except Exception as ex:
                        print(f"[DSF PREP] Nelze smazat {tif_file}: {ex}")
            geotiff_files = filtered_files
            if not geotiff_files:
                QMessageBox.information(None, "Informace", "Žádné dlaždice nezasahují do zadaného čtverce.")
                return

        dds_choice = self.dds_conversion_combo.currentText()
        textures_dir = os.path.join(output_dir, "Textury")
        os.makedirs(textures_dir, exist_ok=True)
        if dds_choice != "None":
            print("[DSF PREP] Zahajuji paralelní DDS konverzi...")
            with ThreadPoolExecutor(max_workers=os.cpu_count()) as executor:
                future_to_file = {}
                for tif_file in geotiff_files:
                    base = os.path.basename(tif_file)
                    name_no_ext, _ = os.path.splitext(base)
                    dds_path = os.path.join(textures_dir, name_no_ext + ".dds")
                    if not os.path.exists(dds_path):
                        future = executor.submit(self.convert_geotiff_to_dds, tif_file, dds_path, dds_choice)
                        future_to_file[future] = tif_file
                for future in as_completed(future_to_file):
                    try:
                        future.result()
                    except Exception as e:
                        print(f"[DSF PREP] Chyba při paralelní konverzi: {e}")
            print("[DSF PREP] Paralelní DDS konverze dokončena.")

        groups = {}
        for tif_file in geotiff_files:
            try:
                from osgeo import gdal
                ds = gdal.Open(tif_file, gdal.GA_ReadOnly)
                if not ds:
                    continue
                gt = ds.GetGeoTransform()
                width = ds.RasterXSize
                height = ds.RasterYSize
                ds = None
                tile_ulx = gt[0]
                tile_n = gt[3]
                tile_e = tile_ulx + width * gt[1]
                tile_s = gt[3] + height * gt[5]
                if tile_s > tile_n:
                    tile_s, tile_n = tile_n, tile_s
                if target_square is not None:
                    cell_west = target_square["west"]
                    cell_east = target_square["east"]
                    cell_south = target_square["south"]
                    cell_north = target_square["north"]
                    inter_w = max(tile_ulx, cell_west)
                    inter_e = min(tile_e, cell_east)
                    inter_s = max(tile_s, cell_south)
                    inter_n = min(tile_n, cell_north)
                    if inter_w < inter_e and inter_s < inter_n:
                        region_code = f"{int(target_square['south']):+03d}{int(target_square['west']):+04d}"
                        groups.setdefault(region_code, []).append((tif_file, (inter_w, inter_s, inter_e, inter_n)))
                else:
                    min_lon = int(math.floor(tile_ulx))
                    max_lon = int(math.floor(tile_e))
                    min_lat = int(math.floor(tile_s))
                    max_lat = int(math.floor(tile_n))
                    for cell_lon in range(min_lon, max_lon + 1):
                        for cell_lat in range(min_lat, max_lat + 1):
                            cell_west = cell_lon
                            cell_east = cell_lon + 1
                            cell_south = cell_lat
                            cell_north = cell_lat + 1
                            inter_w = max(tile_ulx, cell_west)
                            inter_e = min(tile_e, cell_east)
                            inter_s = max(tile_s, cell_south)
                            inter_n = min(tile_n, cell_north)
                            if inter_w < inter_e and inter_s < inter_n:
                                key = f"{cell_lat:+03d}{cell_lon:+04d}"
                                groups.setdefault(key, []).append((tif_file, (inter_w, inter_s, inter_e, inter_n)))
            except Exception as e:
                print(f"[DSF PREP] Chyba při zpracování {tif_file}: {e}")
        if not groups:
            QMessageBox.critical(None, "Chyba", "Nepodařilo se seskupit žádné geotiffy.")
            return

        for region_code, tile_list in groups.items():
            print(f"[DSF PREP] Zpracovávám region {region_code} ({len(tile_list)} dlaždic).")
            try:
                cell_lat = int(region_code[:3])
                cell_lon = int(region_code[3:])
            except Exception as e:
                print(f"[DSF PREP] Chyba při parsování region_code '{region_code}': {e}")
                continue
            north = cell_lat + 1
            south = cell_lat
            east = cell_lon + 1
            west = cell_lon
            dsf_filename = f"dsf_input_{region_code}.txt"
            dsf_txt_path = os.path.join(output_dir, dsf_filename)
                
            try:
                first_tile = tile_list[0][0]
                from osgeo import gdal
                ds_first = gdal.Open(first_tile, gdal.GA_ReadOnly)
                if ds_first:
                    gt = ds_first.GetGeoTransform()
                    width = ds_first.RasterXSize
                    height = ds_first.RasterYSize
                    center_x = gt[0] + (width / 2) * gt[1]
                    center_y = gt[3] + (height / 2) * gt[5]
                    center_lat_rad = center_y * math.pi / 180.0
                    scale_x = width * abs(gt[1]) * 111320 * math.cos(center_lat_rad)
                    scale_y = height * abs(gt[5]) * 111320
                    terrain_size = math.sqrt(scale_x**2 + scale_y**2)
                    texture_resolution = max(width, height)
                    ds_first = None
                else:
                    center_x = center_y = terrain_size = texture_resolution = 0
            except Exception as e:
                print(f"[DSF PREP] Chyba při čtení metadat první dlaždice: {e}")
                center_x = center_y = terrain_size = texture_resolution = 0
                
            with open(dsf_txt_path, "w", encoding="utf-8") as f:
                f.write("A\n")
                f.write("850 Created by SimulatorsCzech orl_cz\n")
                f.write("DRAPED_POLYGON\n\n")
                f.write("DIVISIONS 32\n")
                f.write("HEIGHTS 0.50000 0.0  # max encodeable 32767.50000\n")
                f.write(f"PROPERTY sim/west {west}\n")
                f.write(f"PROPERTY sim/east {east}\n")
                f.write(f"PROPERTY sim/north {north}\n")
                f.write(f"PROPERTY sim/south {south}\n")
                f.write(f"PROPERTY sim/planet {self.planet_combo.currentText()}\n")
                f.write("PROPERTY sim/creation_agent SimulatrosCzech_orto by orl_cz\n")
                f.write("PROPERTY laminar/internal_revision 0\n")
                f.write("PROPERTY sim/overlay 1\n")
                f.write("PROPERTY sim/require_facade 6/0\n\n")
                pol_dict = {}
                next_index = 0
                for (tif_file, bounds) in tile_list:
                    pol_path = self.create_pol_file(tif_file, output_dir)
                    pol_name = os.path.basename(pol_path)
                    if pol_name not in pol_dict:
                        pol_dict[pol_name] = next_index
                        next_index += 1
                for pol_name, idx in pol_dict.items():
                    f.write(f"POLYGON_DEF textury/{pol_name}\n")
                f.write("\n")
                for (tif_file, inter_bounds) in tile_list:
                    pol_path = self.create_pol_file(tif_file, output_dir)
                    pol_name = os.path.basename(pol_path)
                    texture_index = pol_dict[pol_name]
                    (w, s, e, n) = inter_bounds
                    f.write(f"BEGIN_POLYGON {texture_index} 65535 4\n")
                    f.write("BEGIN_WINDING\n")
                    f.write(f"POLYGON_POINT {w:.9f} {s:.9f} 0.000000000 0.000000000\n")
                    f.write(f"POLYGON_POINT {e:.9f} {s:.9f} 1.000000000 0.000000000\n")
                    f.write(f"POLYGON_POINT {e:.9f} {n:.9f} 1.000000000 1.000000000\n")
                    f.write(f"POLYGON_POINT {w:.9f} {n:.9f} 0.000000000 1.000000000\n")
                    f.write("END_WINDING\n")
                    f.write("END_POLYGON\n")
                f.write("\n# LOAD_CENTER v .pol je pouze v definici textury (viz .pol soubor)\n")
            print(f"[DSF PREP] DSF soubor pro region {region_code} vytvořen: {dsf_txt_path}")
        self.status_label.setText("Konverze dokončena. DSF vstupní soubory vytvořeny.")
        self.progress_bar.setValue(100)

    def on_process_button_clicked(self):
        self.progress_bar.setValue(0)
        self.status_label.setText("Probíhá konverze, čekejte prosím...")
        self.run_conversion()
        self.process_button.setEnabled(True)

    def setup_ui(self, parent: QWidget) -> QWidget:
        widget = QWidget(parent)
        main_layout = QVBoxLayout(widget)
        
        title = QLabel("<h2>DSF Příprava Inputu</h2>", widget)
        main_layout.addWidget(title)
        
        info = QLabel("Tento plugin vytvoří DSF vstupní soubor a .pol soubory z konečných ořezaných geotiffů. "
                     "Geotiffy jsou seskupeny dle 1°×1° oblastí. Každý DSF soubor je pojmenován podle oblasti (např. +50+015).", widget)
        info.setWordWrap(True)
        main_layout.addWidget(info)
        
        group_input = QGroupBox("Vstupní adresář (geotiffy)", widget)
        layout_input = QHBoxLayout(group_input)
        self.input_dir_edit = QLineEdit(self.config["input_dir"], widget)
        btn_input = QPushButton("...", widget)
        btn_input.clicked.connect(self.select_input_dir)
        layout_input.addWidget(self.input_dir_edit)
        layout_input.addWidget(btn_input)
        main_layout.addWidget(group_input)
        
        group_output = QGroupBox("Výstupní adresář (DSF a .pol soubory)", widget)
        layout_output = QHBoxLayout(group_output)
        self.output_dir_edit = QLineEdit(self.config["output_dir"], widget)
        btn_output = QPushButton("...", widget)
        btn_output.clicked.connect(self.select_output_dir)
        layout_output.addWidget(self.output_dir_edit)
        layout_output.addWidget(btn_output)
        main_layout.addWidget(group_output)
        
        target_group = QGroupBox("Cílový DSF čtverec (volitelné)", widget)
        target_layout = QHBoxLayout(target_group)
        target_layout.addWidget(QLabel("Lat (dolní):", widget))
        self.target_lat_edit = QLineEdit("", widget)
        self.target_lat_edit.setPlaceholderText("např. 50")
        target_layout.addWidget(self.target_lat_edit)
        target_layout.addWidget(QLabel("Lon (levý):", widget))
        self.target_lon_edit = QLineEdit("", widget)
        self.target_lon_edit.setPlaceholderText("např. 10")
        target_layout.addWidget(self.target_lon_edit)
        main_layout.addWidget(target_group)
        
        planet_group = QGroupBox("Planet", widget)
        planet_layout = QHBoxLayout(planet_group)
        self.planet_combo = QComboBox(widget)
        self.planet_combo.addItems(["earth", "mars"])
        planet_layout.addWidget(QLabel("Planet:", widget))
        planet_layout.addWidget(self.planet_combo)
        main_layout.addWidget(planet_group)
        
        dds_group = QGroupBox("DDS Conversion", widget)
        dds_layout = QHBoxLayout(dds_group)
        dds_layout.addWidget(QLabel("DDS Type:", widget))
        self.dds_conversion_combo = QComboBox(widget)
        self.dds_conversion_combo.addItems(["DXT1", "DXT3", "DXT5", "None"])
        self.dds_conversion_combo.setCurrentText("DXT1")
        self.dds_conversion_combo.setToolTip(
            "DXT1: komprese bez alfa\nDXT3: explicitní alfa\nDXT5: interpolovaný alfa\nNone: nepoužít převod (v .pol se vždy zapisuje .dds)"
        )
        dds_layout.addWidget(self.dds_conversion_combo)
        main_layout.addWidget(dds_group)
        
        # Nová sekce – DSF Options pro nastavení LAYER_GROUP beaches
        dsf_options_group = QGroupBox("DSF Options", widget)
        dsf_options_layout = QHBoxLayout(dsf_options_group)
        dsf_options_layout.addWidget(QLabel("Layer Group beaches:", widget))
        self.layer_group_edit = QLineEdit(self.config.get("layer_group_beaches", "1"), widget)
        from PySide6.QtGui import QIntValidator
        # Povolíme záporné hodnoty a 0, nastavíme dolní hranici na -1000 a horní hranici na 1000.
        self.layer_group_edit.setValidator(QIntValidator(-1000, 1000, widget))
        dsf_options_layout.addWidget(self.layer_group_edit)
        main_layout.addWidget(dsf_options_group)
        
        self.process_button = QPushButton("Spustit DSF přípravu", widget)
        self.process_button.clicked.connect(self.on_process_button_clicked)
        main_layout.addWidget(self.process_button)
        
        self.progress_bar = QProgressBar(widget)
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        main_layout.addWidget(self.progress_bar)
        
        self.status_label = QLabel("Připraveno ke spuštění.", widget)
        self.status_label.setWordWrap(True)
        main_layout.addWidget(self.status_label)
        
        main_layout.addStretch()
        return widget

    def execute(self, data):
        pass

if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    test_window = QWidget()
    layout = QVBoxLayout(test_window)
    plugin = DsfPrepPlugin()
    ui = plugin.setup_ui(test_window)
    layout.addWidget(ui)
    test_window.setWindowTitle("DSF Příprava Plugin - Test")
    test_window.resize(800, 600)
    test_window.show()
    sys.exit(app.exec())
# KONEC SOUBORU
