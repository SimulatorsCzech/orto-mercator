"""
Plugin pro ořezání VRT vrstvy podle shapefile.

Tento plugin byl upraven tak, aby krok oříznutí podle shapefile (včetně vytvoření plynulého přechodu s alfa kanálem) byl zcela přeskočen.
Plugin automaticky oznámí své dokončení prostřednictvím signálu shapefile_clip_finished, přičemž jako výstup použije původní VRT vrstvu.
Tímto způsobem lze zajistit kontinuitu zpracovatelského řetězce bez zásahu uživatele.

Autor: [Vaše jméno]
Verze: 1.6 (skip-clip)
"""

import os
import subprocess
import time
import json
from typing import Dict

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QMessageBox,
                               QGroupBox, QPushButton, QProgressBar, QFileDialog,
                               QGridLayout, QLineEdit, QCheckBox)
from PySide6.QtCore import QThread, Signal

from plugins.plugin_base import PluginBase
from plugins.global_context import global_context
from plugins.signal_manager import signal_manager

class ShapefileClipWorker(QThread):
    progress_updated = Signal(int, int)  # aktuální krok, celkem kroků
    clip_finished = Signal(str)          # cesta k "oříznutému" souboru
    clip_error = Signal(str)             # chybová zpráva
    
    def __init__(self, vrt_file: str, shapefile: str, output_file: str, options: Dict[str, any] = None):
        super().__init__()
        self.vrt_file = vrt_file
        self.shapefile = shapefile  # nyní nepoužíváme, ale udržujeme pro konzistenci
        self.output_file = output_file
        self.options = options or {}
        self.is_running = True

    def stop(self):
        self.is_running = False

    def run(self):
        try:
            # V této verzi je krok oříznutí a blendování celkem přeskočen.
            # Místo toho pouze informujeme, že je tento krok dokončen.
            print("Krok oříznutí VRT dle shapefile byl přeskočen.")
            self.progress_updated.emit(1, 1)
            time.sleep(0.2)  # krátká prodleva, aby byl viditelný progress
            self.progress_updated.emit(1,1)
            # Kopírujeme původní vstupní VRT jako výstup (nebo můžete použít původní cestu)
            # a okamžitě oznamujeme dokončení.
            self.clip_finished.emit(self.vrt_file)
        except Exception as e:
            self.clip_error.emit(str(e))

class ShapefileClipPlugin(PluginBase):
    def __init__(self):
        self.config = {
            "enable_clip": True,
            "output_dir": os.path.join("data", "clipped")
        }
        # UI komponenty – odstranili jsme vše, co se týkalo cropování/blendování.
        self.output_dir_edit = None
        self.output_dir_button = None
        self.clip_button = None
        self.cancel_button = None
        self.progress_bar = None
        self.status_label = None
        self.clip_worker = None
        self.is_clipping = False
        self.current_region = None
        self.vrt_file_path = None
        self.clipped_file_path = None
        
        # Připojíme signály (ostatní signály zůstávají nezměněny)
        signal_manager.global_context_updated.connect(self.on_global_context_updated)
        signal_manager.region_changed.connect(self.on_region_changed)
        signal_manager.vrt_created.connect(self.on_vrt_created)

    def name(self) -> str:
        return "Ořezání podle shapefile (přeskočeno)"
    
    def description(self) -> str:
        return ("Plugin, který by prováděl ořezání VRT vrstvy podle shapefile, je nyní deaktivován. "
                "Krok oříznutí je automaticky přeskočen a vstupní VRT se předá dalším pluginům.")
    
    def get_default_config(self) -> dict:
        return self.config
    
    def update_config(self, new_config: dict):
        self.config.update(new_config)
    
    def select_output_dir(self):
        directory = QFileDialog.getExistingDirectory(None, "Vyberte výstupní adresář", self.output_dir_edit.text())
        if directory:
            self.output_dir_edit.setText(directory)
    
    def on_global_context_updated(self, context: dict):
        # V této verzi není potřeba aktuálních aktualizací
        pass
    
    def on_region_changed(self, region_name: str):
        if not region_name:
            return
        self.current_region = region_name
        self.status_label.setText(f"Připraveno ke zpracování VRT vrstvy pro region: {region_name}")
    
    def on_vrt_created(self, vrt_file_path: str):
        if not vrt_file_path:
            return
        self.vrt_file_path = vrt_file_path
        self.status_label.setText(f"Připraveno ke " 
                                   f"zpracování: {os.path.basename(vrt_file_path)} (GeoTIFF vstup)")
        self.clip_button.setEnabled(True)
    
    def on_clip_button_clicked(self):
        if self.is_clipping:
            return
        if not self.vrt_file_path:
            QMessageBox.warning(None, "Chyba", "Není k dispozici žádná VRT vrstva.")
            return
        # I když se ořezávání nepoužívá, ponecháme možnost nastavit výstupní adresář.
        output_dir = os.path.join(self.output_dir_edit.text(), self.current_region)
        os.makedirs(output_dir, exist_ok=True)
        # Výstupní soubor nastavíme na původní VRT (nebo můžeme zkopírovat)
        output_file = os.path.join(output_dir, f"{self.current_region}_ortofoto_clipped.vrt")
        # Vytvoříme worker, který zcela přeskočí ořezávání
        self.clip_worker = ShapefileClipWorker(
            vrt_file=self.vrt_file_path,
            shapefile="",  # není použito
            output_file=output_file
        )
        self.clip_worker.progress_updated.connect(self.on_progress_updated)
        self.clip_worker.clip_finished.connect(self.on_clip_finished)
        self.clip_worker.clip_error.connect(self.on_clip_error)
        self.clip_worker.start()
        self.is_clipping = True
        self.clip_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.status_label.setText(f"Zpracovávám VRT: {os.path.basename(self.vrt_file_path)}")
        self.progress_bar.setValue(0)
    
    def on_cancel_button_clicked(self):
        if not self.is_clipping or not self.clip_worker:
            return
        self.clip_worker.stop()
        self.status_label.setText("Zpracování zrušeno.")
        self.is_clipping = False
        self.clip_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
    
    def on_progress_updated(self, current: int, total: int):
        progress_percent = int(current / total * 100) if total > 0 else 0
        self.progress_bar.setValue(progress_percent)
        self.status_label.setText(f"Zpracování VRT: {os.path.basename(self.vrt_file_path)} ({current}/{total})")
    
    def on_clip_finished(self, output_file: str):
        self.status_label.setText(f"Zpracování dokončeno: {os.path.basename(output_file)}")
        self.is_clipping = False
        self.clip_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.progress_bar.setValue(100)
        self.clipped_file_path = output_file
        global_context["clipped_vrt_file_path"] = output_file
        global_context["clip_enabled"] = True
        signal_manager.shapefile_clip_finished.emit(output_file)
        # Nepoužíváme tvorbu náhledu, ale pokud chcete, můžete volat create_png_from_clipped.
        QMessageBox.information(None, "Zpracování dokončeno", f"Zpracování pro region {self.current_region} bylo úspěšné.\nVýstup: {output_file}")
    
    def on_clip_error(self, error_message: str):
        self.status_label.setText(f"Chyba při zpracování: {error_message}")
        self.is_clipping = False
        self.clip_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        signal_manager.processing_error.emit(f"Chyba při zpracování VRT vrstvy: {error_message}")
    
    def setup_ui(self, parent: QWidget) -> QWidget:
        widget = QWidget(parent)
        layout = QVBoxLayout(widget)
        title = QLabel("<h2>Ořezání VRT vrstvy – krok přeskočen</h2>", widget)
        layout.addWidget(title)
        info = QLabel("Tento plugin by normálně prováděl ořezání VRT podle shapefile, ale tento krok byl automaticky přeskočen. "
                     "Výstupní VRT zůstává beze změny a je ihned předán dalším pluginům.", widget)
        info.setWordWrap(True)
        layout.addWidget(info)
        clip_group = QGroupBox("Nastavení", widget)
        clip_layout = QGridLayout()
        
        output_dir_label = QLabel("Výstupní adresář:", widget)
        self.output_dir_edit = QLineEdit(self.config["output_dir"], widget)
        self.output_dir_button = QPushButton("...", widget)
        self.output_dir_button.setMaximumWidth(30)
        self.output_dir_button.clicked.connect(self.select_output_dir)
        output_dir_layout = QHBoxLayout()
        output_dir_layout.addWidget(self.output_dir_edit)
        output_dir_layout.addWidget(self.output_dir_button)
        clip_layout.addWidget(output_dir_label, 0, 0)
        clip_layout.addLayout(output_dir_layout, 0, 1)
        
        clip_group.setLayout(clip_layout)
        layout.addWidget(clip_group)
        
        process_group = QGroupBox("Zpracovávací informace", widget)
        process_layout = QVBoxLayout()
        self.progress_bar = QProgressBar(widget)
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        process_layout.addWidget(self.progress_bar)
        self.status_label = QLabel("Připraveno ke zpracování VRT vrstvy.", widget)
        process_layout.addWidget(self.status_label)
        
        buttons_layout = QHBoxLayout()
        self.clip_button = QPushButton("Spustit zpracování", widget)
        self.clip_button.clicked.connect(self.on_clip_button_clicked)
        self.clip_button.setEnabled(False)
        self.cancel_button = QPushButton("Zrušit", widget)
        self.cancel_button.clicked.connect(self.on_cancel_button_clicked)
        self.cancel_button.setEnabled(False)
        buttons_layout.addWidget(self.clip_button)
        buttons_layout.addWidget(self.cancel_button)
        process_layout.addLayout(buttons_layout)
        process_group.setLayout(process_layout)
        layout.addWidget(process_group)
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
    plugin = ShapefileClipPlugin()
    ui = plugin.setup_ui(test_window)
    test_layout.addWidget(ui)
    test_window.show()
    sys.exit(app.exec())
# KONEC SOUBORU