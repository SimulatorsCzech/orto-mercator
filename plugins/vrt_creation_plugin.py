"""
GeoTIFF (EPSG:3857) se dlaždice reprojektují do EPSG:4326 a až potom se sestaví VRT.

Plugin pro tvorbu VRT vrstvy ze stažených ortofoto dlaždic.

Tento plugin nyní pracuje s in-memory workflow – mezioperační data se nedrží na disku, nýbrž pomocí GDAL /vsimem/ mechanismu. 
Na disku tak máte pouze vstupní PNG a finální TIFF. Operace (PNG->GeoTIFF, volitelný downscale, barevná korekce a reprojekce) probíhají sekvenčně.
 
Autor: [Vaše jméno]
Verze: 1.5+ s in-memory zpracováním, barevnou korekcí a živým náhledem
"""

import os
import json
import time
import re
import unicodedata
from typing import List, Dict, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QMessageBox,
                               QGroupBox, QPushButton, QProgressBar, QComboBox,
                               QFileDialog, QGridLayout, QLineEdit, QCheckBox,
                               QSlider, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem,
                               QDialog, QDialogButtonBox)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QPixmap, QImage

# Namísto externích příkazů voláme GDAL API přímo
from osgeo import gdal
import numpy as np
from PIL import Image, ImageEnhance

from plugins.plugin_base import PluginBase
from plugins.global_context import global_context
from plugins.signal_manager import signal_manager

def sanitize_filename(name: str) -> str:
    """
    Sanitizuje řetězec tak, že:
      - převede znaky s diakritikou na jejich základní ASCII verze,
      - nahradí mezery pomlčkami,
      - odstraní zbývající nepovolené znaky, ponechá pouze A-Za-z0-9, pomlčky a podtržítka.
    
    Výsledek: "Bařice-Velké Těšany-Obec" -> "Barice-Velke-Tesany-Obec"
    """
    # Převede diakritiku a další speciální znaky na odpovídající ASCII verze.
    normalized = unicodedata.normalize('NFKD', name).encode('ASCII', 'ignore').decode('ASCII')
    # Nahrazení mezer pomlčkami
    normalized = normalized.replace(" ", "-")
    # Odstraní ostatní nepovolené znaky, ponechá jen písmena, čísla, podtržítka a pomlčky.
    return re.sub(r'[^A-Za-z0-9_-]', '', normalized)

def map_resampling_method(method: str) -> str:
    """
    Převede název metody resamplingu na hodnotu podporovanou GDAL.
    Pokud je metoda "nearest", vrátí "near", jinak vrátí původní hodnotu.
    """
    method = method.lower().strip()
    if method == "nearest":
        return "near"
    return method

# Pomocná funkce pro načtení obsahu paměťového (vsimem) souboru
def read_vsifile(filepath: str) -> bytes:
    """
    Otevře soubor z /vsimem/ a načte celý jeho obsah.
    """
    fp = gdal.VSIFOpenL(filepath, "rb")
    if fp is None:
        raise Exception(f"Nelze otevřít {filepath} pro čtení.")
    # Přesun na konec a zjištění velikosti
    gdal.VSIFSeekL(fp, 0, 2)
    filesize = gdal.VSIFTellL(fp)
    gdal.VSIFSeekL(fp, 0, 0)
    data = gdal.VSIFReadL(1, filesize, fp)
    gdal.VSIFCloseL(fp)
    return data

# Třída pro aplikaci barevné korekce na obrázek
class ColorCorrection:
    def __init__(self):
        self.brightness = 1.0  # 0.0 - 2.0, výchozí 1.0
        self.contrast = 1.0    # 0.0 - 2.0, výchozí 1.0
        self.saturation = 1.0  # 0.0 - 2.0, výchozí 1.0
        self.gamma = 1.0       # 0.1 - 3.0, výchozí 1.0
    
    def apply_to_image(self, image: Image.Image) -> Image.Image:
        """Aplikuje barevnou korekci na PIL Image."""
        # Jas
        if self.brightness != 1.0:
            image = ImageEnhance.Brightness(image).enhance(self.brightness)
        
        # Kontrast
        if self.contrast != 1.0:
            image = ImageEnhance.Contrast(image).enhance(self.contrast)
        
        # Sytost
        if self.saturation != 1.0:
            image = ImageEnhance.Color(image).enhance(self.saturation)
        
        # Gamma korekce
        if self.gamma != 1.0:
            # Převod na numpy array pro gamma korekci
            img_array = np.array(image).astype(np.float32) / 255.0
            img_array = np.power(img_array, 1.0 / self.gamma) * 255.0
            img_array = np.clip(img_array, 0, 255).astype(np.uint8)
            image = Image.fromarray(img_array)
        
        return image
    
    def to_dict(self) -> Dict:
        """Převede nastavení do slovníku pro uložení."""
        return {
            "brightness": self.brightness,
            "contrast": self.contrast,
            "saturation": self.saturation,
            "gamma": self.gamma
        }
    
    def from_dict(self, data: Dict):
        """Načte nastavení ze slovníku."""
        self.brightness = data.get("brightness", 1.0)
        self.contrast = data.get("contrast", 1.0)
        self.saturation = data.get("saturation", 1.0)
        self.gamma = data.get("gamma", 1.0)

# Dialog pro ukládání a načítání nastavení barevné korekce
class ColorCorrectionPresetDialog(QDialog):
    def __init__(self, parent=None, presets=None, current_settings=None):
        super().__init__(parent)
        self.setWindowTitle("Správa předvoleb barevné korekce")
        self.presets = presets or {}
        self.current_settings = current_settings or {}
        
        layout = QVBoxLayout(self)
        
        # Pole pro název nové předvolby
        preset_name_layout = QHBoxLayout()
        preset_name_layout.addWidget(QLabel("Název předvolby:"))
        self.preset_name_edit = QLineEdit()
        preset_name_layout.addWidget(self.preset_name_edit)
        layout.addLayout(preset_name_layout)
        
        # Tlačítko pro uložení aktuálního nastavení
        save_button = QPushButton("Uložit aktuální nastavení")
        save_button.clicked.connect(self.save_preset)
        layout.addWidget(save_button)
        
        # Seznam existujících předvoleb
        self.presets_combo = QComboBox()
        self.update_presets_list()
        layout.addWidget(QLabel("Existující předvolby:"))
        layout.addWidget(self.presets_combo)
        
        # Tlačítka pro načtení a smazání předvolby
        preset_buttons_layout = QHBoxLayout()
        load_button = QPushButton("Načíst vybranou předvolbu")
        load_button.clicked.connect(self.load_preset)
        delete_button = QPushButton("Smazat vybranou předvolbu")
        delete_button.clicked.connect(self.delete_preset)
        preset_buttons_layout.addWidget(load_button)
        preset_buttons_layout.addWidget(delete_button)
        layout.addLayout(preset_buttons_layout)
        
        # Standardní tlačítka dialogu
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def update_presets_list(self):
        """Aktualizuje seznam předvoleb v comboboxu."""
        self.presets_combo.clear()
        for name in self.presets.keys():
            self.presets_combo.addItem(name)
    
    def save_preset(self):
        """Uloží aktuální nastavení jako novou předvolbu."""
        name = self.preset_name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Chyba", "Zadejte název předvolby.")
            return
        
        self.presets[name] = self.current_settings.copy()
        self.update_presets_list()
        self.preset_name_edit.clear()
        QMessageBox.information(self, "Úspěch", f"Předvolba '{name}' byla uložena.")
    
    def load_preset(self):
        """Načte vybranou předvolbu."""
        name = self.presets_combo.currentText()
        if not name:
            QMessageBox.warning(self, "Chyba", "Vyberte předvolbu k načtení.")
            return
        
        preset_data = self.presets.get(name)
        if not preset_data:
            QMessageBox.warning(self, "Chyba", f"Předvolba '{name}' nebyla nalezena.")
            return
        
        self.current_settings.update(preset_data)
        self.accept()  # Zavře dialog s úspěšným výsledkem
    
    def delete_preset(self):
        """Smaže vybranou předvolbu."""
        name = self.presets_combo.currentText()
        if not name:
            QMessageBox.warning(self, "Chyba", "Vyberte předvolbu ke smazání.")
            return
        
        if name in self.presets:
            del self.presets[name]
            self.update_presets_list()
            QMessageBox.information(self, "Úspěch", f"Předvolba '{name}' byla smazána.")

# Třída pro živý náhled obrázku s aplikovanou barevnou korekcí
class LivePreviewWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        
        # Grafická scéna pro zobrazení obrázku
        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene)
        self.view.setMinimumSize(300, 300)
        self.pixmap_item = QGraphicsPixmapItem()
        self.scene.addItem(self.pixmap_item)
        
        self.layout.addWidget(self.view)
        self.layout.addWidget(QLabel("Živý náhled barevné korekce"))
        
        # Původní obrázek a aktuální barevná korekce
        self.original_image = None
        self.color_correction = ColorCorrection()
        
        # Timer pro omezení frekvence aktualizací náhledu
        self.update_timer = QTimer()
        self.update_timer.setSingleShot(True)
        self.update_timer.timeout.connect(self.update_preview)
    
    def set_image(self, image_path: str):
        """Nastaví obrázek pro náhled."""
        try:
            self.original_image = Image.open(image_path)
            self.update_preview()
        except Exception as e:
            print(f"Chyba při načítání obrázku pro náhled: {e}")
    
    def set_color_correction(self, color_correction: ColorCorrection):
        """Nastaví objekt barevné korekce."""
        self.color_correction = color_correction
        self.schedule_update()
    
    def schedule_update(self):
        """Naplánuje aktualizaci náhledu s omezením frekvence."""
        if not self.update_timer.isActive():
            self.update_timer.start(100)  # 100ms zpoždění
    
    def update_preview(self):
        """Aktualizuje náhled s aktuálním nastavením barevné korekce."""
        if self.original_image is None:
            return
        
        try:
            # Aplikace barevné korekce
            corrected_image = self.color_correction.apply_to_image(self.original_image.copy())
            
            # Převod PIL Image na QPixmap
            img_array = np.array(corrected_image)
            height, width, channels = img_array.shape
            bytes_per_line = channels * width
            
            if channels == 3:  # RGB
                qimg = QImage(img_array.data, width, height, bytes_per_line, QImage.Format_RGB888)
            elif channels == 4:  # RGBA
                qimg = QImage(img_array.data, width, height, bytes_per_line, QImage.Format_RGBA8888)
            else:
                return
            
            pixmap = QPixmap.fromImage(qimg)
            
            # Nastavení pixmapy do scény a přizpůsobení zobrazení
            self.pixmap_item.setPixmap(pixmap)
            self.view.fitInView(self.pixmap_item, Qt.KeepAspectRatio)
            self.scene.setSceneRect(self.pixmap_item.boundingRect())
        except Exception as e:
            print(f"Chyba při aktualizaci náhledu: {e}")
    
    def resizeEvent(self, event):
        """Přizpůsobí náhled při změně velikosti widgetu."""
        super().resizeEvent(event)
        if self.pixmap_item.pixmap():
            self.view.fitInView(self.pixmap_item, Qt.KeepAspectRatio)

# -------------------------------
# VRTCreationWorker – konverze PNG dlaždic do GeoTIFF s vloženými geoinformacemi,
# volitelný downscale, barevná korekce a reprojekce do WGS84, vše prováděno v paměti pomocí /vsimem/
# -------------------------------
class VRTCreationWorker(QThread):
    progress_updated = Signal(int, int)  # (aktuální krok, celkem kroků)
    vrt_created = Signal(str)            # (cesta ke VRT souboru)
    creation_error = Signal(str)         # (chybová zpráva)
    
    # Timeout pro jednotlivou konverzi (v sekundách)
    TILE_CONVERSION_TIMEOUT = 600
    
    def __init__(self, tiles: List[str], output_file: str, options: Dict[str, any] = None):
        super().__init__()
        self.tiles = tiles
        self.output_file = output_file
        self.options = options or {}
        self.is_running = True

    def stop(self):
        """Zastaví vytvoření VRT vrstvy."""
        self.is_running = False

    def convert_tile(self, tile: str) -> Optional[str]:
        """
        Převede jeden PNG soubor na GeoTIFF se CRS EPSG:3857, provede volitelný downscale, 
        barevnou korekci a reprojekci do EPSG:4326.
        Všechny kroky se provádějí v paměti pomocí GDAL /vsimem/ a na disku bude vytvořen pouze finální TIFF.
        Vrací cestu k finálnímu TIFF s reprojekcí nebo None.
        """
        max_attempts = self.options.get("max_tile_conversion_attempts", 3)
        attempt = 0
        
        while attempt < max_attempts:
            try:
                # Vytvoříme sanitizovaný základní identifikátor pro /vsimem/ soubory
                base_name = os.path.splitext(os.path.basename(tile))[0]
                base_name = sanitize_filename(base_name)
                mem_prefix = f"/vsimem/{base_name}"
                
                # 1) Konverze PNG -> GeoTIFF (EPSG:3857) pomocí GDAL Translate – vytvoříme dataset v paměti
                translate_options = gdal.TranslateOptions(format="GTiff", outputSRS="EPSG:3857")
                ds_3857 = gdal.Translate(mem_prefix + "_merc.tif", tile, options=translate_options)
                if ds_3857 is None:
                    raise Exception(f"Konverze {tile} do GeoTIFF selhala.")
                ds_3857 = None  # Zavřeme dataset – soubor je v /vsimem/
                
                # 2) Kontrola počtu kanálů; pokud je méně než 4, přidáme alfa kanál pomocí gdal.Warp
                ds_temp = gdal.Open(mem_prefix + "_merc.tif")
                if ds_temp is None:
                    raise Exception("Nelze otevřít GDAL dataset z /vsimem/ po konverzi.")
                band_count = ds_temp.RasterCount
                ds_temp = None
                if band_count < 4:
                    warp_opts_alpha = gdal.WarpOptions(format="GTiff", dstAlpha=True)
                    ds_alpha = gdal.Warp(mem_prefix + "_merc_alpha.tif", mem_prefix + "_merc.tif", options=warp_opts_alpha)
                    if ds_alpha is None:
                        raise Exception("Přidání alfa kanálu selhalo.")
                    ds_alpha = None
                    # Přepíšeme původní soubor v paměti – načteme obsah pomocí read_vsifile
                    buffer = read_vsifile(mem_prefix + "_merc_alpha.tif")
                    gdal.Unlink(mem_prefix + "_merc.tif")
                    gdal.FileFromMemBuffer(mem_prefix + "_merc.tif", buffer)
                    gdal.Unlink(mem_prefix + "_merc_alpha.tif")
                
                # 3) Volitelný downscale, pokud je zadán – provádí se pomocí gdal.Warp s cílovým rozlišením
                if self.options.get("downscale"):
                    downscale_val = float(self.options["downscale"])
                    downscale_method = map_resampling_method(self.options.get("downscale_resampling", "lanczos"))
                    warp_opts_downscale = gdal.WarpOptions(format="GTiff",
                                                           xRes=downscale_val,
                                                           yRes=downscale_val,
                                                           resampleAlg=downscale_method)
                    ds_downscaled = gdal.Warp(mem_prefix + "_merc_ds.tif", mem_prefix + "_merc.tif", options=warp_opts_downscale)
                    if ds_downscaled is None:
                        raise Exception("Downscale selhal.")
                    ds_downscaled = None
                    # Přepíšeme původní dataset v paměti – načteme obsah z dočasného souboru
                    buffer = read_vsifile(mem_prefix + "_merc_ds.tif")
                    gdal.Unlink(mem_prefix + "_merc.tif")
                    gdal.FileFromMemBuffer(mem_prefix + "_merc.tif", buffer)
                    gdal.Unlink(mem_prefix + "_merc_ds.tif")
                
                # 4) Aplikace barevné korekce, pokud je nastavena
                color_correction = self.options.get("color_correction")
                if color_correction and (color_correction.brightness != 1.0 or 
                                         color_correction.contrast != 1.0 or 
                                         color_correction.saturation != 1.0 or 
                                         color_correction.gamma != 1.0):
                    # Načtení datasetu do PIL Image
                    ds_temp = gdal.Open(mem_prefix + "_merc.tif")
                    if ds_temp is None:
                        raise Exception("Nelze otevřít dataset pro barevnou korekci.")
                    
                    # Převod GDAL datasetu na PIL Image
                    width = ds_temp.RasterXSize
                    height = ds_temp.RasterYSize
                    bands = ds_temp.RasterCount
                    
                    # Načtení dat z jednotlivých pásem
                    if bands == 4:  # RGBA
                        r_band = ds_temp.GetRasterBand(1).ReadAsArray()
                        g_band = ds_temp.GetRasterBand(2).ReadAsArray()
                        b_band = ds_temp.GetRasterBand(3).ReadAsArray()
                        a_band = ds_temp.GetRasterBand(4).ReadAsArray()
                        img_array = np.stack((r_band, g_band, b_band, a_band), axis=2)
                    else:  # RGB nebo jiný počet pásem
                        r_band = ds_temp.GetRasterBand(1).ReadAsArray()
                        g_band = ds_temp.GetRasterBand(2).ReadAsArray()
                        b_band = ds_temp.GetRasterBand(3).ReadAsArray()
                        img_array = np.stack((r_band, g_band, b_band), axis=2)
                    
                    ds_temp = None  # Zavřeme dataset
                    
                    # Vytvoření PIL Image
                    if bands == 4:
                        pil_img = Image.fromarray(img_array, 'RGBA')
                    else:
                        pil_img = Image.fromarray(img_array, 'RGB')
                    
                    # Aplikace barevné korekce
                    corrected_img = color_correction.apply_to_image(pil_img)
                    
                    # Převod zpět na numpy array
                    corrected_array = np.array(corrected_img)
                    
                    # Vytvoření nového GDAL datasetu s korigovanými daty
                    driver = gdal.GetDriverByName('GTiff')
                    color_corrected_ds = driver.Create(mem_prefix + "_color_corrected.tif", 
                                                      width, height, bands, gdal.GDT_Byte)
                    
                    # Zápis dat do jednotlivých pásem
                    for i in range(bands):
                        band = color_corrected_ds.GetRasterBand(i+1)
                        band.WriteArray(corrected_array[:, :, i])
                    
                    # Kopírování georeference
                    ds_temp = gdal.Open(mem_prefix + "_merc.tif")
                    color_corrected_ds.SetGeoTransform(ds_temp.GetGeoTransform())
                    color_corrected_ds.SetProjection(ds_temp.GetProjection())
                    ds_temp = None
                    
                    # Uložení a zavření datasetu
                    color_corrected_ds.FlushCache()
                    color_corrected_ds = None
                    
                    # Přepíšeme původní dataset korigovaným
                    buffer = read_vsifile(mem_prefix + "_color_corrected.tif")
                    gdal.Unlink(mem_prefix + "_merc.tif")
                    gdal.FileFromMemBuffer(mem_prefix + "_merc.tif", buffer)
                    gdal.Unlink(mem_prefix + "_color_corrected.tif")
                
                # 5) Reprojekce do WGS84 (EPSG:4326) pomocí gdal.Warp.
                # Zachováváme rozměry podle původního datasetu
                ds_temp = gdal.Open(mem_prefix + "_merc.tif")
                if ds_temp is None:
                    raise Exception("Nelze otevřít dataset v paměti pro reprojekci.")
                input_width = ds_temp.RasterXSize
                input_height = ds_temp.RasterYSize
                ds_temp = None
                nodata = self.options.get("nodata")
                warp_opts_reproj = gdal.WarpOptions(format="GTiff",
                                                    dstSRS="EPSG:4326",
                                                    srcSRS="EPSG:3857",
                                                    resampleAlg=map_resampling_method(self.options.get("resampling", "nearest")),
                                                    width=input_width,
                                                    height=input_height,
                                                    dstNodata=nodata if nodata is not None else None)
                ds_wgs84 = gdal.Warp(mem_prefix + "_wgs84.tif", mem_prefix + "_merc.tif", options=warp_opts_reproj)
                if ds_wgs84 is None:
                    raise Exception("Reprojekce selhala.")
                ds_wgs84 = None
                
                # Volitelně smažeme mezivýstup Mercator dataset z paměti, pokud je nastavena volba smazání
                if self.options.get("delete_mercator", False):
                    gdal.Unlink(mem_prefix + "_merc.tif")
                
                # Finální výstup uložíme z /vsimem/ na disk
                ds_final = gdal.Open(mem_prefix + "_wgs84.tif")
                if ds_final is None:
                    raise Exception("Nelze otevřít reprojektovaný dataset.")
                driver = gdal.GetDriverByName("GTiff")
                # Získáme původní název, sanitizujeme pouze základ
                original_basename = os.path.basename(tile)
                base, _ = os.path.splitext(original_basename)
                base = sanitize_filename(base)
                out_tile = os.path.join(os.path.dirname(tile), f"{base}_wgs84.tif")
                driver.CreateCopy(out_tile, ds_final)
                ds_final = None
                # Uvolníme paměťový soubor
                gdal.Unlink(mem_prefix + "_wgs84.tif")
                return out_tile
            except Exception as e:
                print(f"Pokus {attempt+1}/{max_attempts} selhal u dlaždice {tile}: {e}")
                attempt += 1
                if attempt < max_attempts:
                    time.sleep(1)
        print(f"Všechny pokusy o konverzi dlaždice {tile} selhaly po {max_attempts} pokusech.")
        return None
    def run(self):
        try:
            reprojected_tiles = []
            total_tiles = len(self.tiles)
            max_workers = min(os.cpu_count(), total_tiles) if total_tiles > 0 else os.cpu_count()
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_tile = {executor.submit(self.convert_tile, tile): tile for tile in self.tiles}
                completed = 0
                for future in as_completed(future_to_tile):
                    if not self.is_running:
                        return
                    try:
                        result = future.result(timeout=self.TILE_CONVERSION_TIMEOUT)
                    except TimeoutError:
                        print(f"Konverze dlaždice {future_to_tile[future]} vypršela (timeout).")
                        result = None
                    except Exception as ex:
                        print(f"Chyba u dlaždice {future_to_tile[future]}: {ex}")
                        result = None
                    completed += 1
                    self.progress_updated.emit(completed, total_tiles * 2)
                    if result:
                        reprojected_tiles.append(result)
            
            if len(reprojected_tiles) == 0:
                raise Exception("Žádná dlaždice nebyla úspěšně převedena a reprojektována.")
            
            # Seznam pro vytvoření VRT – uloží se na disk jen finální TIFF
            tiles_list_file = os.path.join(os.path.dirname(self.output_file), "tiles_list.txt")
            with open(tiles_list_file, "w", encoding="utf-8") as f:
                for tile in reprojected_tiles:
                    f.write(f"{tile}\n")
            
            cmd_vrt = ["gdalbuildvrt"]
            rez = self.options.get("resolution")
            if rez == "highest":
                cmd_vrt.extend(["-resolution", "highest"])
            elif rez == "lowest":
                cmd_vrt.extend(["-resolution", "lowest"])
            cmd_vrt.extend([self.output_file, "--optfile", tiles_list_file])
            print(f"Spouštím tvorbu VRT pomocí: {' '.join(cmd_vrt)}")
            self.progress_updated.emit(total_tiles + 1, total_tiles * 2)
            # Pro vytvoření VRT používáme externí volání (jen finální soubory na disku)
            os.system(" ".join(cmd_vrt))
            self.progress_updated.emit(total_tiles * 2, total_tiles * 2)
            os.remove(tiles_list_file)
            
            # Odstraníme extra kanál v případě potřeby (finální VRT)
            fixed_vrt = os.path.splitext(self.output_file)[0] + "_fixed.vrt"
            cmd_fix = ["gdal_translate", "-of", "VRT", "-b", "1", "-b", "2", "-b", "3", "-b", "4", self.output_file, fixed_vrt]
            print(f"Odstraňuji extra kanál pomocí: {' '.join(cmd_fix)}")
            os.system(" ".join(cmd_fix))
            os.replace(fixed_vrt, self.output_file)
            
            if self.options.get("create_jpg", True):
                jpg_output = os.path.splitext(self.output_file)[0] + ".jpg"
                cmd_jpg = ["gdal_translate", "-of", "JPEG", "-co", "PHOTOMETRIC=RGB", "-outsize", "10000", "10000", self.output_file, jpg_output]
                print(f"Vytvářím JPEG s rozměry 10000x10000 pomocí: {' '.join(cmd_jpg)}")
                try:
                    os.system(" ".join(cmd_jpg))
                    print(f"JPEG vytvořen: {jpg_output}")
                except Exception as e:
                    print(f"Chyba při vytváření JPEG: {e}")
            
            self.vrt_created.emit(self.output_file)
            
        except Exception as e:
            self.creation_error.emit(str(e))


# -------------------------------
# VRTCreationPlugin – GUI pro tvorbu VRT se vstupními dlaždicemi v EPSG:3857, s následnou reprojekcí do EPSG:4326
# S podporou in-memory zpracování, barevné korekce a živého náhledu.
# -------------------------------
class VRTCreationPlugin(PluginBase):
    def __init__(self):
        self.config = {
            "resolution": "highest",      # highest, lowest, average
            "compression": "NONE",        # NONE, LZW, JPEG, PACKBITS
            "output_dir": os.path.join("data", "vrt"),
            "max_tile_conversion_attempts": 3,
            "color_correction_presets": {}  # Slovník pro ukládání předvoleb barevné korekce
        }
        self.resolution_combo = None
        self.compression_combo = None
        self.resampling_combo = None
        self.nodata_edit = None
        self.downscale_edit = None
        self.downscale_resampling_combo = None
        self.output_dir_edit = None
        self.output_dir_button = None
        self.create_button = None
        self.cancel_button = None
        self.progress_bar = None
        self.status_label = None
        self.jpg_checkbox = None
        self.delete_png_checkbox = None
        self.delete_mercator_checkbox = None
        
        # Nové komponenty pro barevnou korekci
        self.brightness_slider = None
        self.contrast_slider = None
        self.saturation_slider = None
        self.gamma_slider = None
        self.brightness_value_label = None
        self.contrast_value_label = None
        self.saturation_value_label = None
        self.gamma_value_label = None
        self.preview_widget = None
        self.color_correction = ColorCorrection()
        self.preset_button = None
        
        self.vrt_worker = None
        self.is_creating = False
        self.current_region = None
        self.vrt_file_path = None
        self.preview_image_path = None

    def name(self) -> str:
        return "Tvorba VRT vrstvy s reprojekcí do WGS84"
    
    def description(self) -> str:
        return ("Plugin pro tvorbu VRT ze stažených ortofoto dlaždic. "
                "Vstupní PNG se převedou do GeoTIFF pomocí in-memory GDAL API, "
                "následně se volitelně provede downscale, barevná korekce a každá dlaždice reprojektována do EPSG:4326 "
                "se zachováním původního počtu pixelů. "
                "Finální výsledek je uložen na disk, mezioperační data se zpracovávají v paměti."
                "\nVolitelně lze vytvořit JPEG náhled, smazat původní PNG, smazat mezioperační Mercator TIFF, "
                "volitelně volit metodiku resamplingu pro reprojekci i downscale a zadat nodata hodnotu (výchozí: 0)."
                "\nNově lze provést barevnou korekci (jas, kontrast, sytost, gamma) s živým náhledem.")
    
    def get_default_config(self) -> dict:
        return self.config
    
    def update_config(self, new_config: dict):
        self.config.update(new_config)
    
    def select_output_dir(self):
        directory = QFileDialog.getExistingDirectory(None, "Vyberte výstupní adresář", self.output_dir_edit.text())
        if directory:
            self.output_dir_edit.setText(directory)
    
    def on_region_changed(self, region_name: str):
        self.current_region = region_name
        if hasattr(self, "status_label") and self.status_label is not None:
            self.status_label.setText(f"Připraveno ke zpracování dlaždic pro region: {self.current_region}")
        self.update_preview_image()
    
    def on_ortofoto_download_finished(self, region_name: str, downloaded_tiles: List[str]):
        if not region_name or not downloaded_tiles:
            return
        self.current_region = region_name
        if hasattr(self, "status_label") and self.status_label is not None:
            self.status_label.setText(f"Připraveno ke zpracování dlaždic pro region: {region_name} ({len(downloaded_tiles)} dlaždic)")
        if hasattr(self, "create_button") and self.create_button is not None:
            self.create_button.setEnabled(True)
        self.update_preview_image()
    
    def update_preview_image(self):
        """Aktualizuje náhledový obrázek ze středu oblasti."""
        if not self.current_region or not hasattr(self, "preview_widget") or self.preview_widget is None:
            return
        
        downloaded_tiles = global_context.get("ortofoto_tiles", [])
        if not downloaded_tiles:
            return
        
        # Najdeme dlaždici ze středu oblasti
        middle_index = len(downloaded_tiles) // 2
        if middle_index < len(downloaded_tiles):
            self.preview_image_path = downloaded_tiles[middle_index]
            self.preview_widget.set_image(self.preview_image_path)
    
    def on_brightness_changed(self, value):
        """Callback pro změnu jasu."""
        brightness = value / 100.0  # Převod z 0-200 na 0.0-2.0
        self.color_correction.brightness = brightness
        self.brightness_value_label.setText(f"{brightness:.2f}")
        if self.preview_widget:
            self.preview_widget.set_color_correction(self.color_correction)
    
    def on_contrast_changed(self, value):
        """Callback pro změnu kontrastu."""
        contrast = value / 100.0  # Převod z 0-200 na 0.0-2.0
        self.color_correction.contrast = contrast
        self.contrast_value_label.setText(f"{contrast:.2f}")
        if self.preview_widget:
            self.preview_widget.set_color_correction(self.color_correction)
    
    def on_saturation_changed(self, value):
        """Callback pro změnu sytosti."""
        saturation = value / 100.0  # Převod z 0-200 na 0.0-2.0
        self.color_correction.saturation = saturation
        self.saturation_value_label.setText(f"{saturation:.2f}")
        if self.preview_widget:
            self.preview_widget.set_color_correction(self.color_correction)
    
    def on_gamma_changed(self, value):
        """Callback pro změnu gamma."""
        gamma = value / 100.0  # Převod z 10-300 na 0.1-3.0
        self.color_correction.gamma = gamma
        self.gamma_value_label.setText(f"{gamma:.2f}")
        if self.preview_widget:
            self.preview_widget.set_color_correction(self.color_correction)
    
    def on_preset_button_clicked(self):
        """Otevře dialog pro správu předvoleb barevné korekce."""
        dialog = ColorCorrectionPresetDialog(
            parent=None,
            presets=self.config.get("color_correction_presets", {}),
            current_settings=self.color_correction.to_dict()
        )
        
        if dialog.exec() == QDialog.Accepted:
            # Načtení vybrané předvolby
            self.color_correction.from_dict(dialog.current_settings)
            
            # Aktualizace sliderů
            self.brightness_slider.setValue(int(self.color_correction.brightness * 100))
            self.contrast_slider.setValue(int(self.color_correction.contrast * 100))
            self.saturation_slider.setValue(int(self.color_correction.saturation * 100))
            self.gamma_slider.setValue(int(self.color_correction.gamma * 100))
            
            # Aktualizace náhledu
            if self.preview_widget:
                self.preview_widget.set_color_correction(self.color_correction)
        
        # Uložení aktualizovaných předvoleb do konfigurace
        self.config["color_correction_presets"] = dialog.presets
    
    def on_create_button_clicked(self):
        if self.is_creating:
            return
        if not self.current_region:
            QMessageBox.warning(None, "Chyba", "Není vybrán žádný region.")
            return
        downloaded_tiles = global_context.get("ortofoto_tiles")
        if not downloaded_tiles:
            QMessageBox.warning(None, "Chyba", "Nejsou k dispozici žádné stažené dlaždice.")
            return
        sanitized_region = sanitize_filename(self.current_region)
        output_dir = os.path.join(self.output_dir_edit.text(), sanitized_region)
        os.makedirs(output_dir, exist_ok=True)
        output_file = os.path.join(output_dir, f"{sanitized_region}_ortofoto.vrt")
        self.vrt_worker = VRTCreationWorker(
            tiles=downloaded_tiles,
            output_file=output_file,
            options={
                "resolution": self.resolution_combo.currentText().lower(),
                "compression": self.compression_combo.currentText().upper(),
                "resampling": self.resampling_combo.currentText().lower(),
                "nodata": self.nodata_edit.text().strip(),
                "downscale": self.downscale_edit.text().strip(),
                "downscale_resampling": self.downscale_resampling_combo.currentText().lower(),
                "color_correction": self.color_correction,  # Předáme objekt barevné korekce
                "create_jpg": self.jpg_checkbox.isChecked(),
                "delete_png": self.delete_png_checkbox.isChecked(),
                "delete_mercator": self.delete_mercator_checkbox.isChecked(),
                "max_tile_conversion_attempts": self.config.get("max_tile_conversion_attempts", 3)
            }
        )
        self.vrt_worker.progress_updated.connect(self.on_progress_updated)
        self.vrt_worker.vrt_created.connect(self.on_vrt_created)
        self.vrt_worker.creation_error.connect(self.on_creation_error)
        self.vrt_worker.start()
        self.is_creating = True
        self.create_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        if self.status_label is not None:
            self.status_label.setText(f"Probíhá vytvoření VRT pro region: {self.current_region} (sanitizovaný název: {sanitized_region})")
        self.progress_bar.setValue(0)
    
    def on_cancel_button_clicked(self):
        if not self.is_creating or not self.vrt_worker:
            return
        self.vrt_worker.stop()
        self.vrt_worker.wait()
        if self.status_label is not None:
            self.status_label.setText("Vytváření VRT zrušeno.")
        self.is_creating = False
        self.create_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
    
    def on_progress_updated(self, current: int, total: int):
        progress_percent = int(current / total * 100) if total > 0 else 0
        self.progress_bar.setValue(progress_percent)
        if self.status_label is not None:
            self.status_label.setText(f"Zpracování dlaždic pro {self.current_region} (krok {current}/{total})")
    
    def on_vrt_created(self, vrt_file_path: str):
        if self.status_label is not None:
            self.status_label.setText(f"VRT vytvořeno: {vrt_file_path}")
            print(f"VRT vytvořeno s použitím sanitizovaného názvu regionu: {vrt_file_path}")
        self.is_creating = False
        self.create_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.progress_bar.setValue(100)
        self.vrt_file_path = vrt_file_path
        global_context["vrt_file_path"] = vrt_file_path
        signal_manager.vrt_created.emit(vrt_file_path)
    
    def on_creation_error(self, error_message: str):
        print(f"Chyba při vytváření VRT: {error_message}")
        if self.status_label is not None:
            self.status_label.setText(f"Chyba při vytváření VRT: {error_message}")
        self.is_creating = False
        self.create_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        signal_manager.processing_error.emit(f"Chyba při vytváření VRT vrstvy: {error_message}")
    def setup_ui(self, parent: QWidget) -> QWidget:
        widget = QWidget(parent)
        layout = QVBoxLayout(widget)
        
        title = QLabel("<h2>Tvorba VRT vrstvy s reprojekcí do WGS84</h2>", widget)
        layout.addWidget(title)
        
        info = QLabel("Plugin vytvoří VRT ze stažených ortofoto dlaždic. "
                     "Vstupní PNG se převedou do GeoTIFF pomocí in-memory GDAL API, následně se (volitelně) provede downscale, "
                     "barevná korekce a reprojekce do WGS84. "
                     "Na disku jsou viditelné jen původní PNG a finální TIFF."
                     "\nVolitelně lze vytvořit JPEG náhled, smazat původní PNG, smazat mezioperační Mercator TIFF, "
                     "volitelně volit metodiku resamplingu pro reprojekci i downscale a zadat nodata hodnotu (výchozí: 0).", widget)
        info.setWordWrap(True)
        layout.addWidget(info)
        
        # Hlavní layout pro nastavení a náhled
        main_layout = QHBoxLayout()
        
        # Levá strana - nastavení
        settings_layout = QVBoxLayout()
        
        # Nastavení VRT
        vrt_group = QGroupBox("Nastavení VRT", widget)
        vrt_layout = QGridLayout()
        
        resolution_label = QLabel("Rozlišení:", widget)
        self.resolution_combo = QComboBox(widget)
        self.resolution_combo.addItems(["Highest", "Lowest", "Average"])
        self.resolution_combo.setCurrentText(self.config["resolution"].capitalize())
        vrt_layout.addWidget(resolution_label, 0, 0)
        vrt_layout.addWidget(self.resolution_combo, 0, 1)
        
        compression_label = QLabel("Komprese GeoTIFF:", widget)
        self.compression_combo = QComboBox(widget)
        self.compression_combo.addItems(["NONE", "LZW", "JPEG", "PACKBITS"])
        self.compression_combo.setCurrentText(self.config["compression"])
        vrt_layout.addWidget(compression_label, 1, 0)
        vrt_layout.addWidget(self.compression_combo, 1, 1)
        
        resampling_label = QLabel("Resamplingu (pro reprojekci):", widget)
        self.resampling_combo = QComboBox(widget)
        self.resampling_combo.addItems(["Nearest", "Bilinear", "Cubic", "Cubicspline", "Lanczos"])
        self.resampling_combo.setCurrentText("Nearest")
        vrt_layout.addWidget(resampling_label, 2, 0)
        vrt_layout.addWidget(self.resampling_combo, 2, 1)
        
        nodata_label = QLabel("Nodata hodnota:", widget)
        self.nodata_edit = QLineEdit("0", widget)
        vrt_layout.addWidget(nodata_label, 3, 0)
        vrt_layout.addWidget(self.nodata_edit, 3, 1)
        
        downscale_label = QLabel("Downscale (metry na pixel):", widget)
        self.downscale_edit = QLineEdit("", widget)
        vrt_layout.addWidget(downscale_label, 4, 0)
        vrt_layout.addWidget(self.downscale_edit, 4, 1)
        
        downscale_resampling_label = QLabel("Metoda resamplingu downscale:", widget)
        self.downscale_resampling_combo = QComboBox(widget)
        self.downscale_resampling_combo.addItems(["Nearest", "Bilinear", "Cubic", "Cubicspline", "Lanczos"])
        self.downscale_resampling_combo.setCurrentText("Lanczos")
        vrt_layout.addWidget(downscale_resampling_label, 5, 0)
        vrt_layout.addWidget(self.downscale_resampling_combo, 5, 1)
        
        self.jpg_checkbox = QCheckBox("Vytvořit JPEG náhled 10000x10000", widget)
        self.jpg_checkbox.setChecked(True)
        vrt_layout.addWidget(self.jpg_checkbox, 6, 0, 1, 2)
        
        self.delete_png_checkbox = QCheckBox("Smazat původní PNG po vytvoření GeoTIFFu", widget)
        self.delete_png_checkbox.setChecked(False)
        vrt_layout.addWidget(self.delete_png_checkbox, 7, 0, 1, 2)
        
        self.delete_mercator_checkbox = QCheckBox("Smazat původní Mercator TIFF po reprojekci", widget)
        self.delete_mercator_checkbox.setChecked(False)
        vrt_layout.addWidget(self.delete_mercator_checkbox, 8, 0, 1, 2)
        
        output_dir_label = QLabel("Výstupní adresář:", widget)
        self.output_dir_edit = QLineEdit(self.config["output_dir"], widget)
        self.output_dir_button = QPushButton("...", widget)
        self.output_dir_button.setMaximumWidth(30)
        self.output_dir_button.clicked.connect(self.select_output_dir)
        output_dir_layout = QHBoxLayout()
        output_dir_layout.addWidget(self.output_dir_edit)
        output_dir_layout.addWidget(self.output_dir_button)
        vrt_layout.addWidget(output_dir_label, 9, 0)
        vrt_layout.addLayout(output_dir_layout, 9, 1)
        
        vrt_group.setLayout(vrt_layout)
        settings_layout.addWidget(vrt_group)
        
        # Nastavení barevné korekce
        color_group = QGroupBox("Barevná korekce", widget)
        color_layout = QGridLayout()
        
        # Jas
        brightness_label = QLabel("Jas:", widget)
        self.brightness_slider = QSlider(Qt.Horizontal, widget)
        self.brightness_slider.setMinimum(0)
        self.brightness_slider.setMaximum(200)
        self.brightness_slider.setValue(100)  # Výchozí hodnota 1.0 (100%)
        self.brightness_slider.setTickPosition(QSlider.TicksBelow)
        self.brightness_slider.setTickInterval(10)
        self.brightness_value_label = QLabel("1.00", widget)
        self.brightness_slider.valueChanged.connect(self.on_brightness_changed)
        color_layout.addWidget(brightness_label, 0, 0)
        color_layout.addWidget(self.brightness_slider, 0, 1)
        color_layout.addWidget(self.brightness_value_label, 0, 2)
        
        # Kontrast
        contrast_label = QLabel("Kontrast:", widget)
        self.contrast_slider = QSlider(Qt.Horizontal, widget)
        self.contrast_slider.setMinimum(0)
        self.contrast_slider.setMaximum(200)
        self.contrast_slider.setValue(100)  # Výchozí hodnota 1.0 (100%)
        self.contrast_slider.setTickPosition(QSlider.TicksBelow)
        self.contrast_slider.setTickInterval(10)
        self.contrast_value_label = QLabel("1.00", widget)
        self.contrast_slider.valueChanged.connect(self.on_contrast_changed)
        color_layout.addWidget(contrast_label, 1, 0)
        color_layout.addWidget(self.contrast_slider, 1, 1)
        color_layout.addWidget(self.contrast_value_label, 1, 2)
        
        # Sytost
        saturation_label = QLabel("Sytost:", widget)
        self.saturation_slider = QSlider(Qt.Horizontal, widget)
        self.saturation_slider.setMinimum(0)
        self.saturation_slider.setMaximum(200)
        self.saturation_slider.setValue(100)  # Výchozí hodnota 1.0 (100%)
        self.saturation_slider.setTickPosition(QSlider.TicksBelow)
        self.saturation_slider.setTickInterval(10)
        self.saturation_value_label = QLabel("1.00", widget)
        self.saturation_slider.valueChanged.connect(self.on_saturation_changed)
        color_layout.addWidget(saturation_label, 2, 0)
        color_layout.addWidget(self.saturation_slider, 2, 1)
        color_layout.addWidget(self.saturation_value_label, 2, 2)
        
        # Gamma
        gamma_label = QLabel("Gamma:", widget)
        self.gamma_slider = QSlider(Qt.Horizontal, widget)
        self.gamma_slider.setMinimum(10)
        self.gamma_slider.setMaximum(300)
        self.gamma_slider.setValue(100)  # Výchozí hodnota 1.0 (100%)
        self.gamma_slider.setTickPosition(QSlider.TicksBelow)
        self.gamma_slider.setTickInterval(10)
        self.gamma_value_label = QLabel("1.00", widget)
        self.gamma_slider.valueChanged.connect(self.on_gamma_changed)
        color_layout.addWidget(gamma_label, 3, 0)
        color_layout.addWidget(self.gamma_slider, 3, 1)
        color_layout.addWidget(self.gamma_value_label, 3, 2)
        
        # Tlačítko pro správu předvoleb
        self.preset_button = QPushButton("Správa předvoleb barevné korekce", widget)
        self.preset_button.clicked.connect(self.on_preset_button_clicked)
        color_layout.addWidget(self.preset_button, 4, 0, 1, 3)
        
        color_group.setLayout(color_layout)
        settings_layout.addWidget(color_group)
        
        # Vytváření VRT
        create_group = QGroupBox("Vytváření VRT", widget)
        create_layout = QVBoxLayout()
        
        self.progress_bar = QProgressBar(widget)
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        create_layout.addWidget(self.progress_bar)
        
        self.status_label = QLabel("Připraveno ke zpracování.", widget)
        create_layout.addWidget(self.status_label)
        
        buttons_layout = QHBoxLayout()
        self.create_button = QPushButton("Vytvořit VRT vrstvu", widget)
        self.create_button.clicked.connect(self.on_create_button_clicked)
        self.create_button.setEnabled(False)
        self.cancel_button = QPushButton("Zrušit vytváření", widget)
        self.cancel_button.clicked.connect(self.on_cancel_button_clicked)
        self.cancel_button.setEnabled(False)
        buttons_layout.addWidget(self.create_button)
        buttons_layout.addWidget(self.cancel_button)
        create_layout.addLayout(buttons_layout)
        
        create_group.setLayout(create_layout)
        settings_layout.addWidget(create_group)
        
        # Přidání nastavení do hlavního layoutu
        main_layout.addLayout(settings_layout, 1)  # Váha 1
        
        # Pravá strana - živý náhled
        preview_layout = QVBoxLayout()
        preview_group = QGroupBox("Živý náhled", widget)
        preview_inner_layout = QVBoxLayout()
        
        # Widget pro živý náhled
        self.preview_widget = LivePreviewWidget(widget)
        preview_inner_layout.addWidget(self.preview_widget)
        
        preview_group.setLayout(preview_inner_layout)
        preview_layout.addWidget(preview_group)
        
        # Přidání náhledu do hlavního layoutu
        main_layout.addLayout(preview_layout, 1)  # Váha 1
        
        # Přidání hlavního layoutu do celkového layoutu
        layout.addLayout(main_layout)
        
        # Přidání roztažitelného prostoru na konec
        layout.addStretch()
        
        # Připojení signálů
        signal_manager.region_changed.connect(self.on_region_changed)
        signal_manager.ortofoto_download_finished.connect(self.on_ortofoto_download_finished)
        
        # Inicializace s aktuálními daty
        current_region = global_context.get("selected_region")
        if current_region:
            self.on_region_changed(current_region)
        downloaded_tiles = global_context.get("ortofoto_tiles")
        if downloaded_tiles:
            self.on_ortofoto_download_finished(global_context.get("ortofoto_region"), downloaded_tiles)
        
        return widget
    
    def execute(self, data):
        pass

if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication
    import sys
    app = QApplication(sys.argv)
    test_window = QWidget()
    test_layout = QVBoxLayout(test_window)
    plugin = VRTCreationPlugin()
    ui = plugin.setup_ui(test_window)
    test_layout.addWidget(ui)
    test_window.show()
    sys.exit(app.exec())