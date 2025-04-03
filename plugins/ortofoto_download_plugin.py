
"""
Plugin pro stahování ortofoto dlaždic z WMS služby ČÚZK.

Tento plugin umožňuje stahování ortofoto dlaždic z WMS služby ČÚZK na základě
axis-aligned extended bbox. Dlaždice jsou stahovány ve formátu PNG pro zachování
průhlednosti a jsou systematicky pojmenovány pro správné řazení.

Funkce:
- Nastavení rozlišení v m/px se zobrazeným přibližným Zoomlevelem
- Výpočet informací o velikosti dat
- Stahování dlaždic s přesahem
- Systematické pojmenování souborů
- Ukládání metadat o stažených dlaždicích
- Opakované pokusy o stažení v případě selhání
- Vytvoření průhledných dlaždic v případě neúspěšného stažení
- Georeferencování stažených PNG souborů pomocí world souborů

VŠECHNA data (vstupní bboxy, shapefile) jsou nyní předpokládána v projekční soustavě WebMercator (EPSG:3857).

Autor: [Vaše jméno]
Verze: 1.3 (aktualizováno)
"""

import os
import math
import time
import urllib.parse
from datetime import datetime
from typing import List, Dict
import requests  # Pro lepší HTTP požadavky
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QMessageBox,
                               QGroupBox, QSpinBox, QComboBox, QPushButton, QProgressBar,
                               QCheckBox, QFileDialog, QGridLayout, QLineEdit, QDoubleSpinBox)
from PySide6.QtCore import Qt, QThread, Signal

from plugins.plugin_base import PluginBase
from plugins.global_context import global_context
from plugins.signal_manager import signal_manager

import re
import unicodedata

# Konfigurování logování
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
formatter = logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s")
handler.setFormatter(formatter)
if not logger.handlers:
    logger.addHandler(handler)

def sanitize_filename(name: str) -> str:
    """
    Odstraní diakritiku, interpunkci a speciální znaky z řetězce,
    ale zachová alfanumerické znaky, podtržítka, pomlčky a tečky.
    Pokud je v řetězci obsažena přípona (oddělená tečkou), zachová ji.
    """
    normalized = unicodedata.normalize("NFKD", name).encode("ASCII", "ignore").decode("ASCII")
    if '.' in normalized:
        base, ext = normalized.rsplit('.', 1)
        base_sanitized = re.sub(r'[^A-Za-z0-9_-]', '', base)
        ext_sanitized = re.sub(r'[^A-Za-z0-9]', '', ext)
        if ext_sanitized:
            return f"{base_sanitized}.{ext_sanitized.lower()}"
        else:
            return base_sanitized
    else:
        return re.sub(r'[^A-Za-z0-9_-]', '', normalized)

# Pokusíme se importovat PIL pro kontrolu obrázků
try:
    from PIL import Image
    PIL_AVAILABLE = True
    logger.info("PIL (Pillow) je k dispozici.")
except ImportError:
    PIL_AVAILABLE = False
    logger.warning("Knihovna PIL (Pillow) není nainstalována. Kontrola obrázků nebude dostupná.")

# Pokusíme se importovat GDAL pro georeferencování
try:
    import gdal
    GDAL_AVAILABLE = True
    logger.info("GDAL je k dispozici.")
except ImportError:
    try:
        from osgeo import gdal
        GDAL_AVAILABLE = True
        logger.info("GDAL (z osgeo) je k dispozici.")
    except ImportError:
        GDAL_AVAILABLE = False
        logger.warning("Knihovna GDAL není nainstalována. Georeferencování bude provedeno pomocí world souborů.")

def resolution_to_zoomlevel(resolution: float, latitude: float = 0) -> float:
    """
    Přibližný výpočet zoom levelu pro WebMercator. 
    Používá vzorec:
      zoom = log2((2 * pi * R * cos(lat))/(256 * resolution))
    kde R = 6378137 m.
    Pro jednoduchost se bere cos(lat)=1 (při ekvátoru).
    """
    R = 6378137
    zoom = math.log2((2 * math.pi * R) / (256 * resolution))
    return zoom

class OrtofotoDownloadWorker(QThread):
    """
    Worker třída pro stahování ortofoto dlaždic v samostatném vlákně.
    Optimalizováno pro paralelní stahování dlaždic pomocí ThreadPoolExecutor.
    """
    
    progress_updated = Signal(int, int)  # (aktuální dlaždice, celkem dlaždic)
    download_finished = Signal()
    download_error = Signal(str, str)  # (url, chybová zpráva)
    tile_downloaded = Signal(str)  # (cesta k souboru)
    
    def __init__(self, wms_url: str, bbox: List[float], tile_size: int, 
                 output_dir: str, region_name: str, resolution: float = 0.25,
                 crs: str = "EPSG:3857", image_format: str = "image/png",
                 max_attempts: int = 3, max_workers: int = 8):
        super().__init__()
        self.wms_url = wms_url
        self.bbox = bbox
        self.tile_size = tile_size
        self.output_dir = output_dir
        self.region_name = region_name
        self.resolution = resolution
        self.crs = crs
        self.image_format = image_format
        self.max_attempts = max_attempts
        self.max_workers = max_workers
        self.is_running = True
        
        self.width_meters = self.bbox[2] - self.bbox[0]
        self.height_meters = self.bbox[3] - self.bbox[1]
        self.width_pixels = int(self.width_meters / self.resolution)
        self.height_pixels = int(self.height_meters / self.resolution)
        self.cols = math.ceil(self.width_pixels / self.tile_size)
        self.rows = math.ceil(self.height_pixels / self.tile_size)
        self.total_tiles = self.cols * self.rows
        os.makedirs(self.output_dir, exist_ok=True)
        self.tiles_metadata = []
        logger.info(f"Inicializace: region='{self.region_name}', total_tiles={self.total_tiles}")
    
    def get_resolution(self) -> float:
        return self.resolution
    
    def stop(self):
        self.is_running = False
        logger.info("Stahování dlaždic bylo zastaveno.")
    
    def create_wms_url(self, bbox: List[float]) -> str:
        width_meters = bbox[2] - bbox[0]
        height_meters = bbox[3] - bbox[1]
        width_pixels = max(1, int(width_meters / self.resolution))
        height_pixels = max(1, int(height_meters / self.resolution))
        width_pixels = min(width_pixels, 4096)
        height_pixels = min(height_pixels, 4096)
        params = {
            "SERVICE": "WMS",
            "VERSION": "1.3.0",
            "REQUEST": "GetMap",
            "LAYERS": "0",
            "STYLES": "",
            "CRS": self.crs,
            "BBOX": ",".join(map(str, bbox)),
            "WIDTH": str(width_pixels),
            "HEIGHT": str(height_pixels),
            "FORMAT": self.image_format,
            "TRANSPARENT": "TRUE"
        }
        url = f"{self.wms_url}?{urllib.parse.urlencode(params)}"
        logger.debug(f"Vytvořen URL pro bbox={bbox}: {url}")
        return url
    
    def create_transparent_tile(self, filepath: str, width: int, height: int):
        if not PIL_AVAILABLE:
            with open(filepath, 'wb') as f:
                f.write(b'')
            logger.info(f"Transparent tile vytvořena (bez PIL): {filepath}")
            return
        try:
            img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
            img.save(filepath, 'PNG')
            logger.info(f"Vytvořena průhledná dlaždice: {filepath}")
        except Exception as e:
            logger.error(f"Chyba při vytváření průhledné dlaždice: {str(e)}")
    
    def create_world_file(self, filepath: str, bbox: List[float], width: int, height: int):
        try:
            minx, miny, maxx, maxy = bbox
            x_res = (maxx - minx) / width
            y_res = (maxy - miny) / height
            x_center = minx + x_res / 2
            y_center = maxy - y_res / 2
            world_content = f"{x_res}\n0.0\n0.0\n{-y_res}\n{x_center}\n{y_center}"
            world_filepath = filepath + ".wld"
            with open(world_filepath, 'w') as f:
                f.write(world_content)
            srs_code = self.crs.split(":")[-1]
            aux_content = f"""<PAMDataset>
  <SRS>EPSG:{srs_code}</SRS>
</PAMDataset>"""
            aux_filepath = filepath + ".aux.xml"
            with open(aux_filepath, 'w') as f:
                f.write(aux_content)
            logger.debug(f"World file vytvořen: {world_filepath}")
            return True
        except Exception as e:
            logger.error(f"Chyba při vytváření world file: {str(e)}")
            return False
    
    def create_georeferenced_png(self, filepath: str, bbox: List[float], width: int, height: int, is_transparent: bool = False):
        try:
            if is_transparent:
                if not PIL_AVAILABLE:
                    logger.error("Nelze vytvořit průhledný obrázek, PIL není k dispozici")
                    return False
                img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
                img.save(filepath, 'PNG')
            filepath_without_ext = os.path.splitext(filepath)[0]
            return self.create_world_file(filepath_without_ext, bbox, width, height)
        except Exception as e:
            logger.error(f"Chyba při vytváření georeferencovaného PNG: {str(e)}")
            return False
    
    def download_tile(self, row: int, col: int, session: requests.Session) -> Dict:
        """
        Stáhne dlaždici pro zadaný řádek a sloupec.
        Vrací slovník s metadaty: filename, bbox, row, col, url, success.
        """
        if not self.is_running:
            logger.info("download_tile: Worker již není aktivní.")
            return None

        minx = self.bbox[0] + col * self.tile_size * self.resolution
        miny = self.bbox[1] + row * self.tile_size * self.resolution
        maxx = min(minx + self.tile_size * self.resolution, self.bbox[2])
        maxy = min(miny + self.tile_size * self.resolution, self.bbox[3])
        tile_bbox = [minx, miny, maxx, maxy]
        url = self.create_wms_url(tile_bbox)
        filename = sanitize_filename(f"{self.region_name}_r{row:04d}_c{col:04d}.png")
        filepath = os.path.join(self.output_dir, filename)

        expected_width = int((maxx - minx) / self.resolution)
        expected_height = int((maxy - miny) / self.resolution)
        expected_width = min(expected_width, 4096)
        expected_height = min(expected_height, 4096)

        logger.info(f"Stahuji dlaždici r={row}, c={col} s bbox={tile_bbox}")
        success = False
        for attempt in range(self.max_attempts):
            temp_filepath = filepath + ".temp"
            try:
                r = session.get(url, timeout=10)
                if r.status_code != 200:
                    raise Exception(f"HTTP chyba: {r.status_code}")
                content_type = r.headers.get('Content-Type', '')
                if 'image/png' not in content_type and 'image/jpeg' not in content_type:
                    raise Exception(f"Neočekávaný typ obsahu: {content_type}")
                with open(temp_filepath, 'wb') as f:
                    f.write(r.content)
                if os.path.getsize(temp_filepath) < 1000:
                    raise Exception("Stažený soubor je příliš malý")
                if PIL_AVAILABLE:
                    try:
                        img = Image.open(temp_filepath)
                        img.verify()
                        img = Image.open(temp_filepath)
                        width, height = img.size
                        width_tolerance = expected_width * 0.2
                        height_tolerance = expected_height * 0.2
                        if abs(width - expected_width) > width_tolerance or abs(height - expected_height) > height_tolerance:
                            raise Exception(f"Neočekávané rozměry obrázku: {width}x{height}, očekáváno: {expected_width}x{expected_height}")
                    except Exception as e:
                        raise Exception(f"Stažený obrázek není validní: {str(e)}")
                os.rename(temp_filepath, filepath)
                filepath_without_ext = os.path.splitext(filepath)[0]
                self.create_world_file(filepath_without_ext, tile_bbox, expected_width, expected_height)
                success = True
                logger.info(f"Dlaždice úspěšně stažena: {filename}")
                break
            except Exception as e:
                logger.warning(f"Pokus {attempt+1}/{self.max_attempts} selhal pro {filename}: {str(e)}")
                if os.path.exists(temp_filepath):
                    os.remove(temp_filepath)
                if os.path.exists(filepath):
                    os.remove(filepath)
                if attempt == self.max_attempts - 1:
                    self.download_error.emit(url, str(e))
                else:
                    time.sleep(0.5)
        if not success:
            success = self.create_georeferenced_png(filepath, tile_bbox, expected_width, expected_height, True)
            if not success and not os.path.exists(filepath):
                self.create_transparent_tile(filepath, expected_width, expected_height)
                filepath_without_ext = os.path.splitext(filepath)[0]
                self.create_world_file(filepath_without_ext, tile_bbox, expected_width, expected_height)
        self.tile_downloaded.emit(filepath)
        logger.debug(f"Metadata dlaždice: {{'filename': '{filename}', 'bbox': {tile_bbox}, 'row': {row}, 'col': {col}, 'url': '{url}', 'success': {success}}}")
        return {
            "filename": filename,
            "bbox": tile_bbox,
            "row": row,
            "col": col,
            "url": url,
            "success": success
        }
    
    def run(self):
        total_tiles = self.total_tiles
        current_tile = 0
        session = requests.Session()
        futures = []
        logger.info("Spouštím paralelní stahování dlaždic...")
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            for row in range(self.rows):
                for col in range(self.cols):
                    if not self.is_running:
                        logger.info("Worker zastavil stahování.")
                        break
                    futures.append(executor.submit(self.download_tile, row, col, session))
            for future in as_completed(futures):
                if not self.is_running:
                    break
                result = future.result()
                if result is not None:
                    self.tiles_metadata.append(result)
                    current_tile += 1
                    self.progress_updated.emit(current_tile, total_tiles)
                    logger.info(f"Stáhnuto {current_tile} / {total_tiles} dlaždic.")
        self.save_metadata()
        logger.info("Stahování dlaždic dokončeno.")
        self.download_finished.emit()
    
    def save_metadata(self):
        metadata = {
            "region_name": self.region_name,
            "bbox": self.bbox,
            "crs": self.crs,
            "resolution": self.resolution,
            "tile_size": self.tile_size,
            "width_meters": self.width_meters,
            "height_meters": self.height_meters,
            "width_pixels": self.width_pixels,
            "height_pixels": self.height_pixels,
            "rows": self.rows,
            "cols": self.cols,
            "total_tiles": self.total_tiles,
            "wms_url": self.wms_url,
            "image_format": self.image_format,
            "max_attempts": self.max_attempts,
            "timestamp": datetime.now().isoformat(),
            "tiles": self.tiles_metadata
        }
        metadata_file = os.path.join(self.output_dir, f"{sanitize_filename(self.region_name)}_metadata.json")
        with open(metadata_file, "w", encoding="utf-8") as f:
            import json
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        logger.info(f"Metadata uložena do: {metadata_file}")

class OrtofotoDownloadPlugin(PluginBase):
    """
    Plugin pro stahování ortofoto dlaždic z WMS služby.
    
    Tento plugin umožňuje stahování ortofoto dlaždic z WMS služby ČÚZK na základě
    axis-aligned extended bbox a jsou ukládány ve formátu PNG pro zachování průhlednosti.
    Stažené dlaždice jsou georeferencovány pomocí world souborů pro další zpracování.
    
    Upozornění: Všechna vstupní data (bbox, shapefile) a výstupní dlaždice jsou nyní
    v projekční soustavě WebMercator (EPSG:3857).
    """
    
    def __init__(self):
        self.config = {
            "wms_url": "https://ags.cuzk.gov.cz/arcgis1/services/ORTOFOTO/MapServer/WMSServer",
            "output_dir": os.path.join("data", "ortofoto"),
            "tile_size": 1024,
            "overlap": 15,
            "resolution": 0.25,
            "max_attempts": 3,
            "download_workers": 8,
            "crs": "EPSG:3857",
            "image_format": "image/png"
        }
        
        self.wms_url_edit = None
        self.output_dir_edit = None
        self.output_dir_button = None
        self.tile_size_combo = None
        self.overlap_spin = None
        self.overlap_meters_label = None
        self.resolution_spin = None
        self.max_attempts_spin = None
        self.download_workers_spin = None
        self.info_button = None
        self.download_button = None
        self.cancel_button = None
        self.progress_bar = None
        self.status_label = None
        self.tiles_count_label = None
        self.data_size_label = None
        self.progress_info_label = None
        # Nově přidaný label pro zobrazení přibližného zoomlevelu
        self.zoomlevel_label = None
        
        self.download_worker = None
        self.is_downloading = False
        self.current_region = None
        self.downloaded_tiles = []
        self.start_time = None
        self.error_count = 0
        
        signal_manager.region_changed.connect(self.on_region_changed)
    
    def name(self) -> str:
        return "Stahování ortofoto dlaždic"
    
    def description(self) -> str:
        return ("Plugin pro stahování ortofoto dlaždic z WMS služby ČÚZK. "
                "Dlaždice jsou stahovány na základě axis-aligned extended bbox a "
                "ukládány ve formátu PNG pro zachování průhlednosti. "
                "Stažené dlaždice jsou georeferencovány pomocí world souborů pro další zpracování.")
    
    def get_default_config(self) -> dict:
        return self.config
    
    def update_config(self, new_config: dict):
        self.config.update(new_config)
    
    def calculate_overlap_meters(self) -> float:
        return self.overlap_spin.value() * self.resolution_spin.value()
    
    def update_overlap_meters_label(self):
        overlap_meters = self.calculate_overlap_meters()
        self.overlap_meters_label.setText(f"({overlap_meters:.2f} m)")
    
    def update_zoomlevel_label(self):
        resolution = self.resolution_spin.value()
        zoom = resolution_to_zoomlevel(resolution)
        self.zoomlevel_label.setText(f"~Zoom level: {zoom:.1f}")
    
    def select_output_dir(self):
        directory = QFileDialog.getExistingDirectory(None, "Vyberte výstupní adresář", self.output_dir_edit.text())
        if directory:
            self.output_dir_edit.setText(directory)
    
    def calculate_data_info(self):
        if not self.current_region:
            QMessageBox.warning(None, "Chyba", "Není vybrán žádný region.")
            return
        
        bbox_aligned_extended = global_context.get("bbox_aligned_extended")
        if not bbox_aligned_extended:
            QMessageBox.warning(None, "Chyba", "Bbox není k dispozici.")
            return
        
        minx = min(p[0] for p in bbox_aligned_extended)
        miny = min(p[1] for p in bbox_aligned_extended)
        maxx = max(p[0] for p in bbox_aligned_extended)
        maxy = max(p[1] for p in bbox_aligned_extended)
        bbox = [minx, miny, maxx, maxy]
        
        width_meters = bbox[2] - bbox[0]
        height_meters = bbox[3] - bbox[1]
        resolution = self.resolution_spin.value()
        width_pixels = int(width_meters / resolution)
        height_pixels = int(height_meters / resolution)
        tile_size = int(self.tile_size_combo.currentText())
        cols = math.ceil(width_pixels / tile_size)
        rows = math.ceil(height_pixels / tile_size)
        total_tiles = cols * rows
        tile_size_mb = (tile_size * tile_size * 4) / (1024 * 1024) * 1.2
        total_size_gb = (total_tiles * tile_size_mb) / 1024
        
        self.tiles_count_label.setText(f"Počet dlaždic: {total_tiles} ({cols}x{rows})")
        self.data_size_label.setText(f"Přibližná velikost dat: {total_size_gb:.2f} GB")
        
        info_text = (
            f"Informace o datech pro region: {self.current_region}\n\n"
            f"Rozměry oblasti: {width_meters:.2f} x {height_meters:.2f} m\n"
            f"Rozlišení: {resolution} m/px\n"
            f"({self.zoomlevel_label.text()})\n"
            f"Rozměry v pixelech: {width_pixels} x {height_pixels} px\n\n"
            f"Velikost dlaždice: {tile_size} x {tile_size} px\n"
            f"Počet dlaždic: {total_tiles} ({cols} x {rows})\n"
            f"Přibližná velikost jedné dlaždice: {tile_size_mb:.2f} MB\n"
            f"Celková přibližná velikost dat: {total_size_gb:.2f} GB\n\n"
            f"Počet pokusů o stažení: {self.max_attempts_spin.value()}\n"
            f"V případě neúspěšného stažení bude vytvořena průhledná dlaždice."
        )
        if GDAL_AVAILABLE:
            info_text += "\n\nDlaždice budou georeferencovány pomocí GDAL."
        else:
            info_text += "\n\nDlaždice budou georeferencovány pomocí world souborů (.wld)."
        
        QMessageBox.information(None, "Informace o datech", info_text)
    
    def on_resolution_changed(self):
        self.update_overlap_meters_label()
        self.update_tiles_count()
        self.update_zoomlevel_label()
    
    def on_region_changed(self, region_name: str):
        if not region_name:
            self.current_region = "Neurčený"
        else:
            self.current_region = region_name
        if hasattr(self, 'status_label') and self.status_label is not None:
            self.status_label.setText(f"Připraveno ke stažení dlaždic pro region: {self.current_region}")
        self.update_tiles_count()
    
    def update_tiles_count(self):
        """Aktualizace počtu dlaždic na základě aktuálního výběru"""
        if not hasattr(self, 'tiles_count_label') or self.tiles_count_label is None:
            # Label ještě nebyl inicializován, přeskočíme aktualizaci
            return
            
        # Nastavíme výchozí hodnoty
        self.tiles_count_label.setText("Počet dlaždic: N/A")
        if hasattr(self, 'data_size_label') and self.data_size_label is not None:
            self.data_size_label.setText("Přibližná velikost dat: N/A")
        
        bbox_aligned_extended = global_context.get("bbox_aligned_extended")
        if not bbox_aligned_extended:
            return
        
        minx = min(p[0] for p in bbox_aligned_extended)
        miny = min(p[1] for p in bbox_aligned_extended)
        maxx = max(p[0] for p in bbox_aligned_extended)
        maxy = max(p[1] for p in bbox_aligned_extended)
        bbox = [minx, miny, maxx, maxy]
        
        width_meters = bbox[2] - bbox[0]
        height_meters = bbox[3] - bbox[1]
        resolution = self.resolution_spin.value()
        width_pixels = int(width_meters / resolution)
        height_pixels = int(height_meters / resolution)
        tile_size = int(self.tile_size_combo.currentText())
        cols = math.ceil(width_pixels / tile_size)
        rows = math.ceil(height_pixels / tile_size)
        total_tiles = cols * rows
        tile_size_mb = (tile_size * tile_size * 4) / (1024 * 1024) * 1.2
        total_size_gb = (total_tiles * tile_size_mb) / 1024
        
        self.tiles_count_label.setText(f"Počet dlaždic: {total_tiles} ({cols}x{rows})")
        if hasattr(self, 'data_size_label') and self.data_size_label is not None:
            self.data_size_label.setText(f"Přibližná velikost dat: {total_size_gb:.2f} GB")
    
    def on_tile_size_changed(self):
        self.update_tiles_count()
    
    def on_download_button_clicked(self):
        if self.is_downloading:
            return
        
        if not self.current_region:
            QMessageBox.warning(None, "Chyba", "Není vybrán žádný region.")
            return
        
        bbox_aligned_extended = global_context.get("bbox_aligned_extended")
        if not bbox_aligned_extended:
            QMessageBox.warning(None, "Chyba", "Bbox není k dispozici.")
            return
        
        minx = min(p[0] for p in bbox_aligned_extended)
        miny = min(p[1] for p in bbox_aligned_extended)
        maxx = max(p[0] for p in bbox_aligned_extended)
        maxy = max(p[1] for p in bbox_aligned_extended)
        bbox = [minx, miny, maxx, maxy]
        
        output_dir = os.path.join(self.output_dir_edit.text(), sanitize_filename(self.current_region))
        os.makedirs(output_dir, exist_ok=True)
        
        self.download_worker = OrtofotoDownloadWorker(
            wms_url=self.wms_url_edit.text(),
            bbox=bbox,
            tile_size=int(self.tile_size_combo.currentText()),
            output_dir=output_dir,
            region_name=self.current_region,
            resolution=self.resolution_spin.value(),
            max_attempts=self.max_attempts_spin.value(),
            crs=self.config["crs"],
            image_format=self.config["image_format"],
            max_workers=self.download_workers_spin.value()
        )
        self.download_worker.progress_updated.connect(self.on_progress_updated)
        self.download_worker.download_finished.connect(self.on_download_finished)
        self.download_worker.download_error.connect(self.on_download_error)
        self.download_worker.tile_downloaded.connect(self.on_tile_downloaded)
        
        self.start_time = time.time()
        self.error_count = 0
        self.downloaded_tiles = []
        self.progress_info_label.setText("Spouštím stahování...")
        
        self.download_worker.start()
        self.is_downloading = True
        self.download_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.status_label.setText(f"Stahování dlaždic pro region: {self.current_region}")
        self.progress_bar.setValue(0)
        signal_manager.ortofoto_download_started.emit(self.current_region)
    
    def on_cancel_button_clicked(self):
        if not self.is_downloading or not self.download_worker:
            return
        self.download_worker.stop()
        self.status_label.setText("Stahování zrušeno.")
        self.is_downloading = False
        self.download_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
    
    def on_progress_updated(self, current: int, total: int):
        elapsed = time.time() - self.start_time if self.start_time is not None else 0
        progress_percent = int(current / total * 100) if total > 0 else 0
        self.progress_bar.setValue(progress_percent)
        detail_text = (f"Region: {self.current_region} | "
                       f"Stáhnuto: {current}/{total} dlaždic | "
                       f"Chyby: {self.error_count} | "
                       f"Uplynulý čas: {elapsed:.1f} s | "
                       f"{progress_percent}% hotovo")
        self.progress_info_label.setText(detail_text)
        self.status_label.setText(f"Stahování dlaždic pro region: {self.current_region} ({current}/{total})")
        signal_manager.ortofoto_download_progress.emit(current, total)
    
    def on_download_finished(self):
        def sort_key(filepath):
            filename = os.path.basename(filepath)
            try:
                parts = filename.rsplit("_", 2)
                row_part = parts[-2]
                col_part = parts[-1].split('.')[0]
                row = int(row_part.lstrip("r"))
                col = int(col_part.lstrip("c"))
                return (row, col)
            except Exception as e:
                logger.warning(f"Nepodařilo se extrahovat řádek a sloupec z {filename}: {str(e)}")
                return filename
        
        self.downloaded_tiles.sort(key=sort_key)
        self.status_label.setText(f"Stahování dokončeno. Staženo {len(self.downloaded_tiles)} dlaždic.")
        self.is_downloading = False
        self.download_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.progress_bar.setValue(100)
        total_time = time.time() - self.start_time if self.start_time is not None else 0
        final_text = (f"Region: {self.current_region} | "
                      f"Staženo: {len(self.downloaded_tiles)} dlaždic | "
                      f"Chyby: {self.error_count} | "
                      f"Celkový čas: {total_time:.1f} s | "
                      "100% hotovo")
        self.progress_info_label.setText(final_text)
        global_context["ortofoto_tiles"] = self.downloaded_tiles
        global_context["ortofoto_region"] = self.current_region
        global_context["ortofoto_output_dir"] = os.path.join(self.output_dir_edit.text(), sanitize_filename(self.current_region))
        global_context["ortofoto_resolution"] = self.resolution_spin.value()
        signal_manager.ortofoto_download_finished.emit(self.current_region, self.downloaded_tiles)
    
    def on_download_error(self, url: str, error_message: str):
        logger.error(f"Chyba při stahování dlaždice ({url}): {error_message}")
        self.error_count += 1
        signal_manager.processing_error.emit(f"Chyba při stahování dlaždice: {error_message}")
    
    def on_tile_downloaded(self, filepath: str):
        self.downloaded_tiles.append(filepath)
        logger.debug(f"Dlaždice stažena: {filepath}")
    
    def setup_ui(self, parent: QWidget) -> QWidget:
        widget = QWidget(parent)
        layout = QVBoxLayout(widget)
        
        title = QLabel("<h2>Stahování ortofoto dlaždic</h2>", widget)
        layout.addWidget(title)
        
        info = QLabel("Plugin pro stahování ortofoto dlaždic z WMS služby ČÚZK. "
                     "Dlaždice jsou stahovány na základě axis-aligned extended bbox a "
                     "ukládány ve formátu PNG pro zachování průhlednosti. "
                     "Stažené dlaždice jsou georeferencovány pomocí world souborů pro další zpracování.", widget)
        info.setWordWrap(True)
        layout.addWidget(info)
        
        wms_group = QGroupBox("Nastavení WMS", widget)
        wms_layout = QGridLayout()
        
        wms_url_label = QLabel("URL WMS služby:", widget)
        self.wms_url_edit = QLineEdit(self.config["wms_url"], widget)
        self.wms_url_edit.setMinimumWidth(400)
        wms_layout.addWidget(wms_url_label, 0, 0)
        wms_layout.addWidget(self.wms_url_edit, 0, 1)
        
        output_dir_label = QLabel("Výstupní adresář:", widget)
        self.output_dir_edit = QLineEdit(self.config["output_dir"], widget)
        self.output_dir_button = QPushButton("...", widget)
        self.output_dir_button.setMaximumWidth(30)
        self.output_dir_button.clicked.connect(self.select_output_dir)
        output_dir_layout = QHBoxLayout()
        output_dir_layout.addWidget(self.output_dir_edit)
        output_dir_layout.addWidget(self.output_dir_button)
        wms_layout.addWidget(output_dir_label, 1, 0)
        wms_layout.addLayout(output_dir_layout, 1, 1)
        
        wms_group.setLayout(wms_layout)
        layout.addWidget(wms_group)
        
        tiles_group = QGroupBox("Nastavení dlaždic", widget)
        tiles_layout = QGridLayout()
        
        tile_size_label = QLabel("Velikost dlaždice:", widget)
        self.tile_size_combo = QComboBox(widget)
        self.tile_size_combo.addItems(["256", "512", "1024", "2048"])
        self.tile_size_combo.setCurrentText(str(self.config["tile_size"]))
        self.tile_size_combo.currentTextChanged.connect(self.on_tile_size_changed)
        tiles_layout.addWidget(tile_size_label, 0, 0)
        tiles_layout.addWidget(self.tile_size_combo, 0, 1)
        
        resolution_label = QLabel("Rozlišení (m/px):", widget)
        self.resolution_spin = QDoubleSpinBox(widget)
        self.resolution_spin.setMinimum(0.01)
        self.resolution_spin.setMaximum(10.0)
        self.resolution_spin.setSingleStep(0.01)
        self.resolution_spin.setValue(self.config["resolution"])
        self.resolution_spin.setDecimals(2)
        self.resolution_spin.valueChanged.connect(self.on_resolution_changed)
        tiles_layout.addWidget(resolution_label, 1, 0)
        tiles_layout.addWidget(self.resolution_spin, 1, 1)
        
        self.zoomlevel_label = QLabel("", widget)
        self.update_zoomlevel_label()
        tiles_layout.addWidget(self.zoomlevel_label, 1, 2)
        
        overlap_label = QLabel("Přesah dlaždic (px):", widget)
        self.overlap_spin = QSpinBox(widget)
        self.overlap_spin.setMinimum(0)
        self.overlap_spin.setMaximum(100)
        self.overlap_spin.setValue(self.config["overlap"])
        self.overlap_spin.valueChanged.connect(self.update_overlap_meters_label)
        self.overlap_meters_label = QLabel(f"({self.calculate_overlap_meters():.2f} m)", widget)
        overlap_layout = QHBoxLayout()
        overlap_layout.addWidget(self.overlap_spin)
        overlap_layout.addWidget(self.overlap_meters_label)
        overlap_layout.addStretch()
        tiles_layout.addWidget(overlap_label, 2, 0)
        tiles_layout.addLayout(overlap_layout, 2, 1)
        
        max_attempts_label = QLabel("Počet pokusů o stažení:", widget)
        self.max_attempts_spin = QSpinBox(widget)
        self.max_attempts_spin.setMinimum(1)
        self.max_attempts_spin.setMaximum(10)
        self.max_attempts_spin.setValue(self.config["max_attempts"])
        tiles_layout.addWidget(max_attempts_label, 3, 0)
        tiles_layout.addWidget(self.max_attempts_spin, 3, 1)
        
        download_workers_label = QLabel("Max workers (vláken):", widget)
        self.download_workers_spin = QSpinBox(widget)
        self.download_workers_spin.setMinimum(1)
        self.download_workers_spin.setMaximum(32)
        self.download_workers_spin.setValue(self.config["download_workers"])
        tiles_layout.addWidget(download_workers_label, 4, 0)
        tiles_layout.addWidget(self.download_workers_spin, 4, 1)
        
        tiles_group.setLayout(tiles_layout)
        layout.addWidget(tiles_group)
        
        custom_group = QGroupBox("Volitelné možnosti", widget)
        custom_layout = QVBoxLayout()
        self.download_button = QPushButton("Stáhnout dlaždice", widget)
        self.download_button.clicked.connect(self.on_download_button_clicked)
        self.cancel_button = QPushButton("Zrušit stahování", widget)
        self.cancel_button.clicked.connect(self.on_cancel_button_clicked)
        custom_layout.addWidget(self.download_button)
        custom_layout.addWidget(self.cancel_button)
        custom_group.setLayout(custom_layout)
        layout.addWidget(custom_group)
        
        info_group = QGroupBox("Informace", widget)
        info_layout = QVBoxLayout()
        self.tiles_count_label = QLabel("Počet dlaždic: N/A", widget)
        self.data_size_label = QLabel("Přibližná velikost dat: N/A", widget)
        info_layout.addWidget(self.tiles_count_label)
        info_layout.addWidget(self.data_size_label)
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)
        
        self.progress_bar = QProgressBar(widget)
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)
        self.progress_info_label = QLabel("Detailní průběh stahování bude zobrazen zde.", widget)
        self.progress_info_label.setStyleSheet("QLabel { font-family: monospace; }")
        layout.addWidget(self.progress_info_label)
        
        self.status_label = QLabel("Připraveno ke stažení dlaždic.", widget)
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        
        layout.addStretch()
        return widget
    
    def execute(self, data):
        pass

# KONEC SOUBORU
