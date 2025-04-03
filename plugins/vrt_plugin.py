"""
Plugin pro tvorbu VRT vrstvy z dlaždic.
"""

import os
import logging
from typing import List, Dict, Any, Optional

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                              QPushButton, QFileDialog, QMessageBox,
                              QGroupBox, QGridLayout, QSpinBox, QDoubleSpinBox,
                              QComboBox, QCheckBox, QLineEdit, QDialog)
from PySide6.QtCore import Qt, Slot

# Changed from relative to absolute imports
from plugins.vrt_worker import VRTCreationWorker
from plugins.vrt_progress_dialog import VRTProgressDialog
from plugins.vrt_config import VRTCreationConfig
from plugins.color_correction import ColorCorrection
from plugins.color_correction_dialog import ColorCorrectionDialog

# Nastavení loggeru
logger = logging.getLogger("VRTPlugin")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

class VRTPlugin(QWidget):
    """Plugin pro tvorbu VRT vrstvy z dlaždic"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("VRT Plugin")
        
        # Inicializace proměnných
        self.input_files = []
        self.output_file = ""
        self.worker = None
        self.progress_dialog = None
        self.config = VRTCreationConfig()
        self.color_correction = ColorCorrection()
        
        # Vytvoření GUI
        self.setup_ui()
    
    def setup_ui(self):
        """Vytvoření GUI"""
        main_layout = QVBoxLayout(self)
        
        # Sekce pro výběr vstupních souborů
        input_group = QGroupBox("Vstupní soubory")
        input_layout = QVBoxLayout(input_group)
        
        input_button_layout = QHBoxLayout()
        self.select_files_button = QPushButton("Vybrat soubory...")
        self.select_files_button.clicked.connect(self.on_select_files_clicked)
        input_button_layout.addWidget(self.select_files_button)
        
        self.select_folder_button = QPushButton("Vybrat složku...")
        self.select_folder_button.clicked.connect(self.on_select_folder_clicked)
        input_button_layout.addWidget(self.select_folder_button)
        
        input_layout.addLayout(input_button_layout)
        
        self.files_label = QLabel("Vybráno 0 souborů")
        input_layout.addWidget(self.files_label)
        
        main_layout.addWidget(input_group)
        
        # Sekce pro výběr výstupního souboru
        output_group = QGroupBox("Výstupní soubor")
        output_layout = QHBoxLayout(output_group)
        
        self.output_edit = QLineEdit()
        self.output_edit.setReadOnly(True)
        output_layout.addWidget(self.output_edit)
        
        self.select_output_button = QPushButton("Vybrat...")
        self.select_output_button.clicked.connect(self.on_select_output_clicked)
        output_layout.addWidget(self.select_output_button)
        
        main_layout.addWidget(output_group)
        
        # Sekce pro nastavení
        settings_group = QGroupBox("Nastavení")
        settings_layout = QGridLayout(settings_group)
        
        # Počet vláken
        settings_layout.addWidget(QLabel("Počet vláken:"), 0, 0)
        self.max_workers_spin = QSpinBox()
        self.max_workers_spin.setRange(1, 32)
        self.max_workers_spin.setValue(self.config.max_workers)
        settings_layout.addWidget(self.max_workers_spin, 0, 1)
        
        # Velikost dávky
        settings_layout.addWidget(QLabel("Velikost dávky:"), 1, 0)
        self.batch_size_spin = QSpinBox()
        self.batch_size_spin.setRange(1, 1000)
        self.batch_size_spin.setValue(self.config.batch_size)
        settings_layout.addWidget(self.batch_size_spin, 1, 1)
        
        # Downscale
        settings_layout.addWidget(QLabel("Downscale:"), 0, 2)
        self.downscale_spin = QDoubleSpinBox()
        self.downscale_spin.setRange(0, 100)
        self.downscale_spin.setValue(0)  # 0 znamená žádný downscale
        self.downscale_spin.setSingleStep(0.1)
        settings_layout.addWidget(self.downscale_spin, 0, 3)
        
        # Metoda resamplingu
        settings_layout.addWidget(QLabel("Resampling:"), 1, 2)
        self.resampling_combo = QComboBox()
        resampling_methods = ["nearest", "bilinear", "cubic", "cubicspline", "lanczos", "average", "mode"]
        self.resampling_combo.addItems(resampling_methods)
        self.resampling_combo.setCurrentText(self.config.resampling)
        settings_layout.addWidget(self.resampling_combo, 1, 3)
        
        # Rozlišení
        settings_layout.addWidget(QLabel("Rozlišení:"), 2, 0)
        self.resolution_combo = QComboBox()
        self.resolution_combo.addItems(["highest", "lowest", "average"])
        self.resolution_combo.setCurrentText(self.config.resolution)
        settings_layout.addWidget(self.resolution_combo, 2, 1)
        
        # Vytvoření JPEG náhledu
        settings_layout.addWidget(QLabel("Vytvořit JPEG náhled:"), 2, 2)
        self.create_jpg_check = QCheckBox()
        self.create_jpg_check.setChecked(self.config.create_jpg)
        settings_layout.addWidget(self.create_jpg_check, 2, 3)
        
        # Smazat původní PNG
        settings_layout.addWidget(QLabel("Smazat původní PNG:"), 3, 0)
        self.delete_png_check = QCheckBox()
        self.delete_png_check.setChecked(self.config.delete_png)
        settings_layout.addWidget(self.delete_png_check, 3, 1)
        
        # Barevná korekce
        settings_layout.addWidget(QLabel("Barevná korekce:"), 5, 0)
        self.color_correction_button = QPushButton("Nastavit...")
        self.color_correction_button.clicked.connect(self.on_color_correction_clicked)
        settings_layout.addWidget(self.color_correction_button, 5, 1, 1, 2)
        
        main_layout.addWidget(settings_group)
        
        # Tlačítka
        button_layout = QHBoxLayout()
        
        self.create_button = QPushButton("Vytvořit VRT")
        self.create_button.clicked.connect(self.on_create_clicked)
        self.create_button.setEnabled(False)
        button_layout.addWidget(self.create_button)
        
        main_layout.addLayout(button_layout)
    
    def on_select_files_clicked(self):
        """Obsluha kliknutí na tlačítko pro výběr souborů"""
        files, _ = QFileDialog.getOpenFileNames(
            self, "Vyberte vstupní soubory", "", "PNG soubory (*.png);;Všechny soubory (*.*)"
        )
        
        if files:
            self.input_files = files
            self.files_label.setText(f"Vybráno {len(self.input_files)} souborů")
            self.update_create_button_state()
    
    def on_select_folder_clicked(self):
        """Obsluha kliknutí na tlačítko pro výběr složky"""
        folder = QFileDialog.getExistingDirectory(self, "Vyberte složku se vstupními soubory")
        
        if folder:
            # Najdeme všechny PNG soubory ve složce
            self.input_files = []
            for root, _, files in os.walk(folder):
                for file in files:
                    if file.lower().endswith(".png"):
                        self.input_files.append(os.path.join(root, file))
            
            self.files_label.setText(f"Vybráno {len(self.input_files)} souborů")
            self.update_create_button_state()
    
    def on_select_output_clicked(self):
        """Obsluha kliknutí na tlačítko pro výběr výstupního souboru"""
        file, _ = QFileDialog.getSaveFileName(
            self, "Vyberte výstupní soubor", "", "VRT soubory (*.vrt);;Všechny soubory (*.*)"
        )
        
        if file:
            # Přidáme příponu .vrt, pokud chybí
            if not file.lower().endswith(".vrt"):
                file += ".vrt"
            
            self.output_file = file
            self.output_edit.setText(self.output_file)
            self.update_create_button_state()
    
    def update_create_button_state(self):
        """Aktualizuje stav tlačítka pro vytvoření VRT"""
        self.create_button.setEnabled(len(self.input_files) > 0 and self.output_file != "")
    
    def get_config_from_ui(self) -> VRTCreationConfig:
        """Získá konfiguraci z UI"""
        config = VRTCreationConfig()
        
        config.max_workers = self.max_workers_spin.value()
        config.batch_size = self.batch_size_spin.value()
        
        # Downscale
        downscale_value = self.downscale_spin.value()
        if downscale_value > 0:
            config.downscale = downscale_value
        else:
            config.downscale = None
        
        config.resampling = self.resampling_combo.currentText()
        config.downscale_resampling = config.resampling
        config.resolution = self.resolution_combo.currentText()
        config.create_jpg = self.create_jpg_check.isChecked()
        config.delete_png = self.delete_png_check.isChecked()
        
        # Přidáme barevnou korekci do konfigurace
        if not self.color_correction.is_identity():
            config.color_correction = self.color_correction
        
        return config
    
    def on_create_clicked(self):
        """Obsluha kliknutí na tlačítko pro vytvoření VRT"""
        # Získání konfigurace z UI
        self.config = self.get_config_from_ui()
        
        # Validace konfigurace
        errors = self.config.validate()
        if errors:
            error_message = "Chyba v konfiguraci:\n"
            for field, error in errors.items():
                error_message += f"- {field}: {error}\n"
            
            QMessageBox.critical(self, "Chyba konfigurace", error_message)
            return
        
        # Vytvoření progress dialogu
        self.progress_dialog = VRTProgressDialog(self)
        self.progress_dialog.cancel_requested.connect(self.on_cancel_requested)
        
        # Vytvoření a spuštění workeru
        self.worker = VRTCreationWorker(self.input_files, self.output_file, self.config.to_dict())
        self.worker.progress_updated.connect(self.progress_dialog.update_progress)
        self.worker.status_message.connect(self.progress_dialog.update_status)
        self.worker.vrt_created.connect(self.progress_dialog.handle_completion)
        self.worker.creation_error.connect(self.progress_dialog.handle_error)
        self.worker.start()
        
        # Zobrazení progress dialogu
        self.progress_dialog.exec()
    
    def on_cancel_requested(self):
        """Obsluha požadavku na zrušení zpracování"""
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            
    def on_color_correction_clicked(self):
        """Obsluha kliknutí na tlačítko pro nastavení barevné korekce"""
        dialog = ColorCorrectionDialog(self, self.color_correction)
        if dialog.exec() == QDialog.Accepted:
            self.color_correction = dialog.get_color_correction()