"""
Dialog pro nastavení barevné korekce.
"""

import os
from typing import Optional
from PIL import Image
import numpy as np

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                              QPushButton, QFileDialog, QGroupBox, QGridLayout,
                              QSlider, QDoubleSpinBox)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap, QImage

# Changed from relative to absolute import
from plugins.color_correction import ColorCorrection

class ColorCorrectionDialog(QDialog):
    """Dialog pro nastavení barevné korekce"""
    
    correction_changed = Signal(object)
    
    def __init__(self, parent=None, initial_correction: Optional[ColorCorrection] = None):
        super().__init__(parent)
        self.setWindowTitle("Nastavení barevné korekce")
        self.setMinimumSize(600, 400)
        
        # Inicializace proměnných
        self.color_correction = initial_correction or ColorCorrection()
        self.preview_image = None
        self.preview_image_path = None
        
        # Vytvoření GUI
        self.setup_ui()
        
        # Nastavení hodnot
        self.update_ui_from_correction()
    
    def setup_ui(self):
        """Vytvoření GUI"""
        main_layout = QVBoxLayout(self)
        
        # Horní část - náhled a výběr obrázku
        preview_layout = QHBoxLayout()
        
        # Náhled
        preview_group = QGroupBox("Náhled")
        preview_inner_layout = QVBoxLayout(preview_group)
        
        self.preview_label = QLabel("Vyberte obrázek pro náhled")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumSize(300, 200)
        preview_inner_layout.addWidget(self.preview_label)
        
        self.select_image_button = QPushButton("Vybrat obrázek...")
        self.select_image_button.clicked.connect(self.on_select_image_clicked)
        preview_inner_layout.addWidget(self.select_image_button)
        
        preview_layout.addWidget(preview_group)
        
        main_layout.addLayout(preview_layout)
        
        # Nastavení barevné korekce
        settings_group = QGroupBox("Nastavení barevné korekce")
        settings_layout = QGridLayout(settings_group)
        
        # Jas
        settings_layout.addWidget(QLabel("Jas:"), 0, 0)
        self.brightness_slider = QSlider(Qt.Horizontal)
        self.brightness_slider.setRange(0, 200)
        self.brightness_slider.setValue(100)
        self.brightness_slider.valueChanged.connect(self.on_brightness_changed)
        settings_layout.addWidget(self.brightness_slider, 0, 1)
        
        self.brightness_spin = QDoubleSpinBox()
        self.brightness_spin.setRange(0.01, 2.0)
        self.brightness_spin.setValue(1.0)
        self.brightness_spin.setSingleStep(0.01)
        self.brightness_spin.valueChanged.connect(self.on_brightness_spin_changed)
        settings_layout.addWidget(self.brightness_spin, 0, 2)
        
        # Kontrast
        settings_layout.addWidget(QLabel("Kontrast:"), 1, 0)
        self.contrast_slider = QSlider(Qt.Horizontal)
        self.contrast_slider.setRange(0, 200)
        self.contrast_slider.setValue(100)
        self.contrast_slider.valueChanged.connect(self.on_contrast_changed)
        settings_layout.addWidget(self.contrast_slider, 1, 1)
        
        self.contrast_spin = QDoubleSpinBox()
        self.contrast_spin.setRange(0.01, 2.0)
        self.contrast_spin.setValue(1.0)
        self.contrast_spin.setSingleStep(0.01)
        self.contrast_spin.valueChanged.connect(self.on_contrast_spin_changed)
        settings_layout.addWidget(self.contrast_spin, 1, 2)
        
        # Sytost
        settings_layout.addWidget(QLabel("Sytost:"), 2, 0)
        self.saturation_slider = QSlider(Qt.Horizontal)
        self.saturation_slider.setRange(0, 200)
        self.saturation_slider.setValue(100)
        self.saturation_slider.valueChanged.connect(self.on_saturation_changed)
        settings_layout.addWidget(self.saturation_slider, 2, 1)
        
        self.saturation_spin = QDoubleSpinBox()
        self.saturation_spin.setRange(0.01, 2.0)
        self.saturation_spin.setValue(1.0)
        self.saturation_spin.setSingleStep(0.01)
        self.saturation_spin.valueChanged.connect(self.on_saturation_spin_changed)
        settings_layout.addWidget(self.saturation_spin, 2, 2)
        
        # Gamma
        settings_layout.addWidget(QLabel("Gamma:"), 3, 0)
        self.gamma_slider = QSlider(Qt.Horizontal)
        self.gamma_slider.setRange(10, 300)
        self.gamma_slider.setValue(100)
        self.gamma_slider.valueChanged.connect(self.on_gamma_changed)
        settings_layout.addWidget(self.gamma_slider, 3, 1)
        
        self.gamma_spin = QDoubleSpinBox()
        self.gamma_spin.setRange(0.1, 3.0)
        self.gamma_spin.setValue(1.0)
        self.gamma_spin.setSingleStep(0.01)
        self.gamma_spin.valueChanged.connect(self.on_gamma_spin_changed)
        settings_layout.addWidget(self.gamma_spin, 3, 2)
        
        # Doostření
        settings_layout.addWidget(QLabel("Doostření:"), 4, 0)
        self.sharpen_slider = QSlider(Qt.Horizontal)
        self.sharpen_slider.setRange(0, 100)
        self.sharpen_slider.setValue(0)
        self.sharpen_slider.valueChanged.connect(self.on_sharpen_changed)
        settings_layout.addWidget(self.sharpen_slider, 4, 1)
        
        self.sharpen_spin = QDoubleSpinBox()
        self.sharpen_spin.setRange(0.0, 1.0)
        self.sharpen_spin.setValue(0.0)
        self.sharpen_spin.setSingleStep(0.01)
        self.sharpen_spin.valueChanged.connect(self.on_sharpen_spin_changed)
        settings_layout.addWidget(self.sharpen_spin, 4, 2)
        
        main_layout.addWidget(settings_group)
        
        # Tlačítka
        button_layout = QHBoxLayout()
        
        self.reset_button = QPushButton("Resetovat")
        self.reset_button.clicked.connect(self.on_reset_clicked)
        button_layout.addWidget(self.reset_button)
        
        button_layout.addStretch()
        
        self.cancel_button = QPushButton("Zrušit")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)
        
        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self.accept)
        button_layout.addWidget(self.ok_button)
        
        main_layout.addLayout(button_layout)
    
    # Rest of the class implementation remains the same...
    # (I'm not including the full implementation to keep the response concise)
    
    def update_ui_from_correction(self):
        """Aktualizuje UI podle aktuálního nastavení barevné korekce"""
        # Blokujeme signály, abychom zabránili rekurzivním voláním
        self.brightness_slider.blockSignals(True)
        self.brightness_spin.blockSignals(True)
        self.contrast_slider.blockSignals(True)
        self.contrast_spin.blockSignals(True)
        self.saturation_slider.blockSignals(True)
        self.saturation_spin.blockSignals(True)
        self.gamma_slider.blockSignals(True)
        self.gamma_spin.blockSignals(True)
        self.sharpen_slider.blockSignals(True)
        self.sharpen_spin.blockSignals(True)
        
        # Nastavení hodnot
        self.brightness_slider.setValue(int(self.color_correction.brightness * 100))
        self.brightness_spin.setValue(self.color_correction.brightness)
        
        self.contrast_slider.setValue(int(self.color_correction.contrast * 100))
        self.contrast_spin.setValue(self.color_correction.contrast)
        
        self.saturation_slider.setValue(int(self.color_correction.saturation * 100))
        self.saturation_spin.setValue(self.color_correction.saturation)
        
        self.gamma_slider.setValue(int(self.color_correction.gamma * 100))
        self.gamma_spin.setValue(self.color_correction.gamma)
        
        self.sharpen_slider.setValue(int(self.color_correction.sharpen * 100))
        self.sharpen_spin.setValue(self.color_correction.sharpen)
        
        # Odblokujeme signály
        self.brightness_slider.blockSignals(False)
        self.brightness_spin.blockSignals(False)
        self.contrast_slider.blockSignals(False)
        self.contrast_spin.blockSignals(False)
        self.saturation_slider.blockSignals(False)
        self.saturation_spin.blockSignals(False)
        self.gamma_slider.blockSignals(False)
        self.gamma_spin.blockSignals(False)
        self.sharpen_slider.blockSignals(False)
        self.sharpen_spin.blockSignals(False)
        
        # Aktualizace náhledu
        self.update_preview()
    
    def get_color_correction(self) -> ColorCorrection:
        """Vrátí aktuální nastavení barevné korekce"""
        return self.color_correction