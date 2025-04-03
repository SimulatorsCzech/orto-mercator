import os
import logging
import math
import time

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QFileDialog, QMessageBox
)
from PySide6.QtCore import Qt, QThread, Signal
from osgeo import gdal

from plugins.plugin_base import PluginBase
from plugins.global_context import global_context

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

class GeoTiffWgs84ConversionWorker(QThread):
    progress_updated = Signal(int, int)
    conversion_finished = Signal(str)
    conversion_error = Signal(str)
    
    def __init__(self, input_file: str, output_file: str, tile_size: int):
        """
        :param input_file: Vstupní geotiff v EPSG:3857
        :param output_file: Výstupní soubor, přeprojektovaný do EPSG:4326
        :param tile_size: Nepoužívá se - výstupní obraz zachovává rozměry vstupního obrazu
        """
        super().__init__()
        self.input_file = input_file
        self.output_file = output_file
        self.tile_size = tile_size
        self.is_running = True
    
    def stop(self):
        self.is_running = False
        
    def run(self):
        try:
            logger.info("Spouštím konverzi geotiffu z EPSG:3857 do EPSG:4326.")
            # Ověříme, že vstupní soubor se dá otevřít a získáme jeho rozměry.
            ds = gdal.Open(self.input_file)
            if ds is None:
                raise Exception("Nelze otevřít vstupní dataset.")
            input_width = ds.RasterXSize
            input_height = ds.RasterYSize
            ds = None
            logger.info(f"Vstupní dataset má rozměry: {input_width} x {input_height}")
            
            # Zachováme původní rozměry – tedy výstup bude mít stejný počet pixelů jako vstup.
            target_width = input_width
            target_height = input_height

            # Připravíme volby pro GDAL.Warp:
            warp_options = gdal.WarpOptions(
                dstSRS="EPSG:4326",
                srcSRS="EPSG:3857",
                resampleAlg="cubic",
                width=target_width,
                height=target_height,
                format="GTiff"
            )
            # Spustíme reprojekci a současně zachováme počet pixelů
            out_ds = gdal.Warp(self.output_file, self.input_file, options=warp_options)
            if out_ds is None:
                raise Exception("GDAL.Warp selhalo.")
            # Uzavřeme výsledný dataset
            out_ds = None
            logger.info("Konverze dokončena.")
            self.conversion_finished.emit(self.output_file)
        except Exception as e:
            logger.exception("Chyba při konverzi geotiffu:")
            self.conversion_error.emit(str(e))

class GeoTiffWgs84ConversionPlugin(PluginBase):
    def __init__(self):
        self.input_file_edit = None
        self.output_file_edit = None
        self.tile_size_edit = None
        self.convert_button = None
        self.status_label = None
        self.conversion_worker = None

    def name(self) -> str:
        return "Převod Geotiffu do WGS84"

    def description(self) -> str:
        return ("Plugin převede geotiff v proj. WebMercator (EPSG:3857) do WGS84 (EPSG:4326) s "
                "přímo zachovaným počtem pixelů (např. 2048x2048 dlaždice).")
                
    def get_default_config(self) -> dict:
        return {}

    def update_config(self, new_config: dict):
        pass

    def select_input_file(self):
        file_path, _ = QFileDialog.getOpenFileName(None, "Vyberte vstupní geotiff (EPSG:3857)", "", "GeoTIFF (*.tif *.tiff)")
        if file_path:
            self.input_file_edit.setText(file_path)

    def select_output_file(self):
        file_path, _ = QFileDialog.getSaveFileName(None, "Uložit převedený geotiff (EPSG:4326)", "", "GeoTIFF (*.tif *.tiff)")
        if file_path:
            self.output_file_edit.setText(file_path)

    def on_convert_button_clicked(self):
        input_file = self.input_file_edit.text().strip()
        output_file = self.output_file_edit.text().strip()
        try:
            tile_size = int(self.tile_size_edit.text().strip())
        except Exception:
            tile_size = 2048
        if not input_file or not output_file:
            QMessageBox.warning(None, "Chyba", "Musíte zadat vstupní i výstupní cestu.")
            return
        self.status_label.setText("Spouštím konverzi...")
        self.conversion_worker = GeoTiffWgs84ConversionWorker(input_file, output_file, tile_size)
        self.conversion_worker.conversion_finished.connect(self.on_conversion_finished)
        self.conversion_worker.conversion_error.connect(self.on_conversion_error)
        self.conversion_worker.start()

    def on_conversion_finished(self, output_file: str):
        self.status_label.setText(f"Konverze dokončena: {os.path.basename(output_file)}")
        QMessageBox.information(None, "Dokončeno", f"Konverze geotiffu dokončena:\n{output_file}")

    def on_conversion_error(self, error_message: str):
        self.status_label.setText(f"Chyba: {error_message}")
        QMessageBox.critical(None, "Chyba", f"Chyba při konverzi geotiffu:\n{error_message}")

    def setup_ui(self, parent: QWidget) -> QWidget:
        widget = QWidget(parent)
        layout = QVBoxLayout(widget)
        title = QLabel("<h2>Převod geotiffu z EPSG:3857 do EPSG:4326</h2>", widget)
        layout.addWidget(title)
        
        input_layout = QHBoxLayout()
        input_label = QLabel("Vstupní geotiff (WebMercator):", widget)
        self.input_file_edit = QLineEdit("", widget)
        input_button = QPushButton("...", widget)
        input_button.clicked.connect(self.select_input_file)
        input_layout.addWidget(input_label)
        input_layout.addWidget(self.input_file_edit)
        input_layout.addWidget(input_button)
        layout.addLayout(input_layout)
        
        output_layout = QHBoxLayout()
        output_label = QLabel("Výstupní geotiff (WGS84):", widget)
        self.output_file_edit = QLineEdit("", widget)
        output_button = QPushButton("...", widget)
        output_button.clicked.connect(self.select_output_file)
        output_layout.addWidget(output_label)
        output_layout.addWidget(self.output_file_edit)
        output_layout.addWidget(output_button)
        layout.addLayout(output_layout)
        
        tile_layout = QHBoxLayout()
        tile_label = QLabel("Rozměr dlaždice (px):", widget)
        self.tile_size_edit = QLineEdit("2048", widget)
        tile_layout.addWidget(tile_label)
        tile_layout.addWidget(self.tile_size_edit)
        layout.addLayout(tile_layout)
        
        self.convert_button = QPushButton("Převést", widget)
        self.convert_button.clicked.connect(self.on_convert_button_clicked)
        layout.addWidget(self.convert_button)
        
        self.status_label = QLabel("Připraveno.", widget)
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
    plugin = GeoTiffWgs84ConversionPlugin()
    ui = plugin.setup_ui(test_window)
    test_layout.addWidget(ui)
    test_window.show()
    app.exec()
# KONEC SOUBORU
