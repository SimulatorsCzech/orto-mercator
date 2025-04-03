
"""
Plugin předpokládá, že vstupní VRT je již v EPSG:4326.
Provádí pouze oříznutí dle zadaného bboxu (pokud je definován) a následně data rozdělí na dlaždice.

Autor: [Vaše jméno]
Verze: 1.4 – odstraněna reprojekce z GUI
"""

import os
import subprocess
import math
import time
import json
import random
from io import BytesIO
from typing import Dict, Tuple

from concurrent.futures import ThreadPoolExecutor, as_completed
from pyproj import Transformer

import re
import unicodedata
import logging

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QMessageBox,
                               QGroupBox, QProgressBar, QLineEdit, QGridLayout,
                               QPushButton, QFileDialog, QCheckBox, QComboBox)
from PySide6.QtCore import Qt, QThread, Signal, QRectF
from PySide6.QtGui import QPixmap, QIntValidator, QImage

import numpy as np
from osgeo import gdal
from PIL import Image
import cv2

from plugins.plugin_base import PluginBase
from plugins.global_context import global_context
from plugins.signal_manager import signal_manager

logging.basicConfig(level=logging.DEBUG,
                    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

def sanitize_filename(name: str) -> str:
    normalized = unicodedata.normalize("NFKD", name).encode("ASCII", "ignore").decode("ASCII")
    sanitized = re.sub(r'[^A-Za-z0-9]', '', normalized)
    logger.debug(f"Sanitizing filename: '{name}' -> '{sanitized}'")
    return sanitized

def sanitize_filename_with_extension(filename: str) -> str:
    if '.' in filename:
        base, ext = filename.rsplit('.', 1)
        result = f"{sanitize_filename(base)}.{ext}"
        logger.debug(f"Sanitizing filename with ext: '{filename}' -> '{result}'")
        return result
    else:
        return sanitize_filename(filename)

# ------------------------------
# Worker pro dělení dlaždic
# ------------------------------
class TilingWorker(QThread):
    progress_updated = Signal(int, int)
    tiling_finished = Signal(str, int)
    tiling_error = Signal(str)
    
    def __init__(self, input_file: str, output_dir: str, tile_size: int = 2048, options: Dict[str, any] = None):
        super().__init__()
        self.input_file = input_file
        self.output_dir = output_dir
        self.tile_size = tile_size
        self.options = options or {}
        self.is_running = True
        os.makedirs(self.output_dir, exist_ok=True)

    def stop(self):
        logger.info("TilingWorker zastavován.")
        self.is_running = False

    def get_raster_size(self, raster_file: str) -> Tuple[int, int]:
        ds = gdal.Open(raster_file)
        if ds is None:
            raise Exception("Nebyl možné otevřít rastrový soubor.")
        width = ds.RasterXSize
        height = ds.RasterYSize
        ds = None
        logger.debug(f"Velikost rastrového souboru: {width} x {height}")
        return width, height

    def run(self):
        try:
            logger.info("Spouštím dělení dlaždic s konstantním rozlišením a transparentním paddingem.")
            width, height = self.get_raster_size(self.input_file)
            tile_overlap = int(self.options.get("tile_overlap", 0))
            stride = self.tile_size - tile_overlap if tile_overlap < self.tile_size else self.tile_size
            cols = math.ceil((width - tile_overlap) / stride)
            rows = math.ceil((height - tile_overlap) / stride)
            total_tiles = cols * rows
            region_name = os.path.basename(self.input_file).split("_")[0]
            tasks = []
            with ThreadPoolExecutor(max_workers=os.cpu_count()) as executor:
                for row in range(rows):
                    for col in range(cols):
                        if not self.is_running:
                            logger.info("Dělení dlaždic zastaveno.")
                            return
                        x_off = col * stride
                        y_off = row * stride
                        x_size = self.tile_size
                        y_size = self.tile_size
                        logger.debug(f"Vytvářím dlaždici: {region_name}_r{row:04d}_c{col:04d}.tif se srcWin=[{x_off}, {y_off}, {x_size}, {y_size}]")
                        options = gdal.TranslateOptions(format="GTiff", creationOptions=[
                            f"COMPRESS={self.options.get('compression', 'NONE').upper()}",
                            "TILED=YES", "BIGTIFF=IF_NEEDED"],
                            srcWin=[x_off, y_off, x_size, y_size])
                        tasks.append(executor.submit(gdal.Translate, os.path.join(self.output_dir, sanitize_filename_with_extension(f"{region_name}_r{row:04d}_c{col:04d}.tif")), self.input_file, options=options))
                completed = 0
                for future in as_completed(tasks):
                    if not self.is_running:
                        return
                    result = future.result()
                    if result is None:
                        raise Exception("Chyba při tvorbě dlaždice")
                    completed += 1
                    self.progress_updated.emit(completed, total_tiles)
            logger.info("Dělení dlaždic bylo dokončeno.")
            self.tiling_finished.emit(self.output_dir, total_tiles)
        except Exception as e:
            logger.exception("Chyba při dělení dlaždic:")
            self.tiling_error.emit(str(e))

# ------------------------------
# Hlavní Plugin: ReprojectionPlugin (GUI bez reprojekce)
# ------------------------------
class ReprojectionPlugin(PluginBase):
    def __init__(self):
        # Vstupní VRT je již v EPSG:4326.
        self.config = {
            "tile_size": 2048,
            "tile_overlap": 0,
            "compression": "NONE",
            "output_dir": os.path.join("Vystup")
        }
        signal_manager.vrt_created.connect(self.on_vrt_created)
        self.current_region = None
        self.input_file_path = None  # Vstupní VRT v EPSG:4326
        self.processed_file_path = None
        self.tiling_worker = None
        self.is_processing = False

        # GUI prvky reprojekce byly odstraněny; zůstávají pouze volby pro dělení dlaždic a výstupní adresář.
        self.tile_size_combo = None
        self.tile_overlap_edit = None
        self.output_dir_edit = None
        self.output_dir_button = None
        self.reprocess_button = None  # Tento tlačítko spouští zpracování (ořez a dělení)
        self.cancel_button = None
        self.progress_bar = None
        self.status_label = None

    def name(self) -> str:
        return "Zpracování a dělení dlaždic"
    
    def description(self) -> str:
        return ("Plugin předpokládá, že vstupní VRT je již v EPSG:4326. "
                "Provádí pouze oříznutí dle zadaného bboxu (pokud je definován) a následně data rozdělí na dlaždice.")
    
    def get_default_config(self) -> dict:
        return self.config

    def update_config(self, new_config: dict):
        self.config.update(new_config)
        logger.debug(f"Nová konfigurace: {self.config}")

    def select_output_dir(self):
        directory = QFileDialog.getExistingDirectory(None, "Vyberte výstupní adresář", self.output_dir_edit.text())
        if directory:
            self.output_dir_edit.setText(directory)
            logger.info(f"Vybrán výstupní adresář: {directory}")

    def on_region_changed(self, region_name: str):
        if not region_name:
            return
        self.current_region = region_name
        self.status_label.setText(f"Připraveno ke zpracování pro: {region_name}")
        logger.info(f"Region změněn na: {region_name}")

    def on_vrt_created(self, vrt_file_path: str):
        if not vrt_file_path:
            return
        self.input_file_path = vrt_file_path
        self.status_label.setText(f"Připraven vstup: {os.path.basename(vrt_file_path)}")
        self.reprocess_button.setEnabled(True)
        global_context["clipped_vrt_file_path"] = vrt_file_path
        if not global_context.get("vrt_file_path"):
            global_context["vrt_file_path"] = vrt_file_path
        logger.info(f"VRT vytvořen: {vrt_file_path}")

    def on_reprocess_button_clicked(self):
        """
        Protože vstupní VRT je již v EPSG:4326, provádíme oříznutí (crop).
        Pokud je definován bbox_aligned_100 v global_context, před použitím jej převedeme
        z EPSG:3857 (WebMercator) do EPSG:4326.
        """
        if self.is_processing:
            logger.warning("Již probíhá zpracování.")
            return
        if not self.input_file_path:
            QMessageBox.warning(None, "Chyba", "Vstupní VRT není k dispozici.")
            logger.error("Vstupní VRT není k dispozici.")
            return
        
        output_dir = os.path.join(self.output_dir_edit.text(), sanitize_filename(self.current_region))
        os.makedirs(output_dir, exist_ok=True)
        extension = "vrt"  # Formát se ponechává stejný jako vstup
        processed_file = os.path.join(output_dir, f"{self.current_region}_ortofoto_processed.{extension}")

        logger.info(f"Spouštím zpracování (oříznutí) vstupu: {self.input_file_path}")
        # Pokud je definován bbox_aligned_100, provedeme oříznutí.
        if "bbox_aligned_100" in global_context:
            bbox = global_context["bbox_aligned_100"]
            if bbox and len(bbox) >= 4:
                xs = [p[0] for p in bbox]
                ys = [p[1] for p in bbox]
                orig_xmin, orig_xmax = min(xs), max(xs)
                orig_ymin, orig_ymax = min(ys), max(ys)
                # Protože bbox je v EPSG:3857, převedeme jej do EPSG:4326.
                transformer = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)
                lon_min, lat_min = transformer.transform(orig_xmin, orig_ymin)
                lon_max, lat_max = transformer.transform(orig_xmax, orig_ymax)
                proj_xmin, proj_ymin = lon_min, lat_min
                proj_xmax, proj_ymax = lon_max, lat_max
                output_dir = os.path.dirname(processed_file)
                region_name = os.path.basename(processed_file).split("_")[0]
                cropped_file = os.path.join(output_dir, f"{region_name}_ortofoto_cropped.{extension}")
                cmd_crop = [
                    "gdal_translate", "-q", "-of", extension,
                    "-projwin", str(proj_xmin), str(proj_ymax), str(proj_xmax), str(proj_ymin),
                    self.input_file_path, cropped_file
                ]
                logger.info(f"Spouštím oříznutí pomocí příkazu: {' '.join(cmd_crop)}")
                proc = subprocess.Popen(cmd_crop, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                stdout, stderr = proc.communicate()
                if proc.returncode != 0:
                    raise Exception(f"Chyba při oříznutí: {stderr}")
                processed_file = cropped_file
        else:
            logger.info("bbox_aligned_100 není definován, oříznutí přeskočeno.")

        self.processed_file_path = processed_file
        self.status_label.setText(f"Zpracování dokončeno: {os.path.basename(processed_file)}")
        global_context["reprojected_vrt_file_path"] = processed_file
        self.start_tiling(processed_file)

    def start_tiling(self, input_for_tiling: str):
        logger.info(f"Spouštím dělení dlaždic pro soubor: {input_for_tiling}")
        self.status_label.setText(f"Začíná dělení dlaždic: {os.path.basename(input_for_tiling)}")
        tiles_dir = os.path.join(self.output_dir_edit.text(), sanitize_filename(self.current_region))
        self.tiling_worker = TilingWorker(
            input_file=input_for_tiling,
            output_dir=tiles_dir,
            tile_size=int(self.tile_size_combo.currentText()),
            options={
                "compression": self.config.get("compression", "NONE"),
                "tile_overlap": int(self.tile_overlap_edit.text())
            }
        )
        self.tiling_worker.progress_updated.connect(self.on_tiling_progress_updated)
        self.tiling_worker.tiling_finished.connect(self.on_tiling_finished)
        self.tiling_worker.tiling_error.connect(self.on_tiling_error)
        self.tiling_worker.start()

    def on_cancel_button_clicked(self):
        if not self.is_processing:
            return
        logger.info("Zahajuji rušení zpracování.")
        if self.tiling_worker and self.tiling_worker.isRunning():
            self.tiling_worker.stop()
        self.status_label.setText("Proces byl zrušen.")
        self.is_processing = False

    def on_tiling_progress_updated(self, current: int, total: int):
        progress_percent = 50 + int(current / total * 50) if total > 0 else 50
        self.progress_bar.setValue(progress_percent)
        self.status_label.setText(f"Dlaždice: {current}/{total}")
        logger.debug(f"Dlaždice: {current}/{total} ({progress_percent}%)")

    def on_tiling_finished(self, output_dir: str, tiles_count: int):
        self.status_label.setText(f"Zpracování dokončeno. {tiles_count} dlaždic vytvořeno v: {output_dir}")
        self.is_processing = False
        self.reprocess_button.setEnabled(True)
        self.progress_bar.setValue(100)
        global_context["reprojected_vrt_file_path"] = self.processed_file_path
        global_context["tiles_output_dir"] = output_dir
        global_context["tiles_count"] = tiles_count
        logger.info(f"Dlaždice dokončeny: {tiles_count} v adresáři {output_dir}")
        signal_manager.tiling_finished.emit(output_dir, tiles_count)
        QMessageBox.information(None, "Dokončeno", 
            f"Zpracování pro region {self.current_region} bylo úspěšné.\nDlaždice: {tiles_count} v adresáři: {output_dir}")

    def on_tiling_error(self, error_message: str):
        self.status_label.setText(f"Chyba dělení na dlaždice: {error_message}")
        self.is_processing = False
        self.reprocess_button.setEnabled(True)
        logger.error(f"Chyba dělení dlaždic: {error_message}")
        signal_manager.processing_error.emit(f"Dlaždice: {error_message}")

    def setup_ui(self, parent: QWidget) -> QWidget:
        widget = QWidget(parent)
        layout = QVBoxLayout(widget)
        title = QLabel("<h2>Zpracování a dělení dlaždic</h2>", widget)
        layout.addWidget(title)
        info = QLabel("Plugin předpokládá, že vstupní VRT je v EPSG:4326. "
                     "Provádí oříznutí dle zadaného bboxu (pokud je definován) a následně data rozděluje na dlaždice.", widget)
        info.setWordWrap(True)
        layout.addWidget(info)
        process_group = QGroupBox("Zpracování VRT", widget)
        process_layout = QVBoxLayout()
        self.progress_bar = QProgressBar(widget)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        process_layout.addWidget(self.progress_bar)
        self.status_label = QLabel("Připraveno k zpracování dat.", widget)
        process_layout.addWidget(self.status_label)
        buttons_layout = QHBoxLayout()
        self.reprocess_button = QPushButton("Zpracovat VRT (ořez a dělení)", widget)
        self.reprocess_button.clicked.connect(self.on_reprocess_button_clicked)
        self.reprocess_button.setEnabled(False)
        self.cancel_button = QPushButton("Zrušit zpracování", widget)
        self.cancel_button.clicked.connect(self.on_cancel_button_clicked)
        self.cancel_button.setEnabled(False)
        buttons_layout.addWidget(self.reprocess_button)
        buttons_layout.addWidget(self.cancel_button)
        process_layout.addLayout(buttons_layout)
        process_group.setLayout(process_layout)
        layout.addWidget(process_group)
        tiles_group = QGroupBox("Nastavení dlaždic", widget)
        tiles_layout = QGridLayout()
        tile_size_label = QLabel("Velikost dlaždice (px):", widget)
        self.tile_size_combo = QComboBox(widget)
        self.tile_size_combo.addItems(["256", "512", "1024", "2048", "4096"])
        self.tile_size_combo.setCurrentText(str(self.config["tile_size"]))
        tiles_layout.addWidget(tile_size_label, 0, 0)
        tiles_layout.addWidget(self.tile_size_combo, 0, 1)
        tile_overlap_label = QLabel("Overlap dlaždice (px):", widget)
        self.tile_overlap_edit = QLineEdit(str(self.config.get("tile_overlap", 0)), widget)
        self.tile_overlap_edit.setValidator(QIntValidator(0, 10000, widget))
        tiles_layout.addWidget(tile_overlap_label, 1, 0)
        tiles_layout.addWidget(self.tile_overlap_edit, 1, 1)
        output_dir_label = QLabel("Výstupní adresář:", widget)
        self.output_dir_edit = QLineEdit(self.config["output_dir"], widget)
        self.output_dir_button = QPushButton("...", widget)
        self.output_dir_button.setMaximumWidth(30)
        self.output_dir_button.clicked.connect(self.select_output_dir)
        output_dir_layout = QHBoxLayout()
        output_dir_layout.addWidget(self.output_dir_edit)
        output_dir_layout.addWidget(self.output_dir_button)
        tiles_layout.addWidget(output_dir_label, 2, 0)
        tiles_layout.addLayout(output_dir_layout, 2, 1)
        tiles_group.setLayout(tiles_layout)
        layout.addWidget(tiles_group)
        layout.addStretch()
        signal_manager.region_changed.connect(self.on_region_changed)
        signal_manager.vrt_created.connect(self.on_vrt_created)
        current_region = global_context.get("selected_region")
        if current_region:
            self.on_region_changed(current_region)
        clipped_file = global_context.get("clipped_vrt_file_path")
        if clipped_file:
            self.on_vrt_created(clipped_file)
        return widget

    def execute(self, data):
        pass

if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication
    import sys
    app = QApplication(sys.argv)
    test_window = QWidget()
    from PySide6.QtWidgets import QVBoxLayout
    test_layout = QVBoxLayout(test_window)
    plugin = ReprojectionPlugin()
    ui = plugin.setup_ui(test_window)
    test_layout.addWidget(ui)
    test_window.show()
    logger.info("Spouštím aplikaci.")
    sys.exit(app.exec())
# KONEC SOUBORU
