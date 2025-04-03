"""
Dialog pro zobrazení průběhu zpracování VRT vrstvy.
"""

import os
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                              QProgressBar, QPushButton, QTextEdit, QWidget,
                              QGroupBox, QGridLayout)
from PySide6.QtCore import Qt, Signal, Slot

class VRTProgressDialog(QDialog):
    """Dialog pro zobrazení průběhu zpracování VRT vrstvy"""
    
    cancel_requested = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Vytváření VRT vrstvy")
        self.setMinimumSize(600, 400)
        self.setModal(True)
        
        # Inicializace proměnných
        self.start_time = time.time()
        self.last_status_update = {}
        
        # Vytvoření GUI
        self.setup_ui()
    
    def setup_ui(self):
        """Vytvoření GUI"""
        main_layout = QVBoxLayout(self)
        
        # Sekce s hlavním průběhem
        progress_group = QGroupBox("Průběh zpracování")
        progress_layout = QVBoxLayout(progress_group)
        
        # Hlavní progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        progress_layout.addWidget(self.progress_bar)
        
        # Status zpráva
        self.status_label = QLabel("Inicializace...")
        self.status_label.setWordWrap(True)
        progress_layout.addWidget(self.status_label)
        
        main_layout.addWidget(progress_group)
        
        # Sekce s detailními informacemi
        details_group = QGroupBox("Detailní informace")
        details_layout = QGridLayout(details_group)
        
        # Zpracované soubory
        details_layout.addWidget(QLabel("Zpracováno:"), 0, 0)
        self.processed_label = QLabel("0/0")
        details_layout.addWidget(self.processed_label, 0, 1)
        
        # Úspěšné soubory
        details_layout.addWidget(QLabel("Úspěšných:"), 1, 0)
        self.successful_label = QLabel("0")
        details_layout.addWidget(self.successful_label, 1, 1)
        
        # Neúspěšné soubory
        details_layout.addWidget(QLabel("Neúspěšných:"), 2, 0)
        self.failed_label = QLabel("0")
        details_layout.addWidget(self.failed_label, 2, 1)
        
        # Rychlost zpracování
        details_layout.addWidget(QLabel("Rychlost:"), 0, 2)
        self.speed_label = QLabel("0 souborů/s")
        details_layout.addWidget(self.speed_label, 0, 3)
        
        # Uplynulý čas
        details_layout.addWidget(QLabel("Uplynulý čas:"), 1, 2)
        self.elapsed_label = QLabel("00:00:00")
        details_layout.addWidget(self.elapsed_label, 1, 3)
        
        # Odhadovaný čas dokončení
        details_layout.addWidget(QLabel("Odhadovaný čas dokončení:"), 2, 2)
        self.eta_label = QLabel("--:--:--")
        details_layout.addWidget(self.eta_label, 2, 3)
        
        main_layout.addWidget(details_group)
        
        # Log zpráv
        log_group = QGroupBox("Log zpráv")
        log_layout = QVBoxLayout(log_group)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        log_layout.addWidget(self.log_text)
        
        main_layout.addWidget(log_group)
        
        # Tlačítka
        button_layout = QHBoxLayout()
        
        self.cancel_button = QPushButton("Zrušit")
        self.cancel_button.clicked.connect(self.on_cancel_clicked)
        button_layout.addWidget(self.cancel_button)
        
        main_layout.addLayout(button_layout)
    
    def on_cancel_clicked(self):
        """Obsluha kliknutí na tlačítko Zrušit"""
        self.cancel_button.setEnabled(False)
        self.cancel_button.setText("Zastavuji...")
        self.add_log_message("Požadavek na zastavení zpracování...")
        self.cancel_requested.emit()
    
    def add_log_message(self, message: str):
        """Přidá zprávu do logu"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")
        # Posun na konec
        self.log_text.verticalScrollBar().setValue(self.log_text.verticalScrollBar().maximum())
    
    @Slot(int, int, dict)
    def update_progress(self, current: int, total: int, status_info: Dict[str, Any]):
        """Aktualizuje průběh zpracování"""
        # Aktualizace progress baru
        percent = int((current / max(1, total)) * 100)
        self.progress_bar.setValue(percent)
        
        # Aktualizace detailních informací
        if status_info:
            self.last_status_update = status_info
            
            # Zpracované soubory
            self.processed_label.setText(f"{status_info.get('processed', 0)}/{status_info.get('total', 0)}")
            
            # Úspěšné soubory
            self.successful_label.setText(str(status_info.get('successful', 0)))
            
            # Neúspěšné soubory
            self.failed_label.setText(str(status_info.get('failed', 0)))
            
            # Rychlost zpracov��ní
            speed = status_info.get('processing_speed', 0)
            self.speed_label.setText(f"{speed:.2f} souborů/s")
            
            # Odhadovaný čas dokončení
            eta = status_info.get('estimated_completion')
            if eta:
                self.eta_label.setText(eta.strftime("%H:%M:%S"))
        
        # Aktualizace uplynulého času
        elapsed_seconds = time.time() - self.start_time
        elapsed_time = str(timedelta(seconds=int(elapsed_seconds)))
        self.elapsed_label.setText(elapsed_time)
    
    @Slot(str)
    def update_status(self, message: str):
        """Aktualizuje status zprávu"""
        self.status_label.setText(message)
        self.add_log_message(message)
    
    @Slot(str)
    def handle_error(self, error_message: str):
        """Zpracuje chybovou zprávu"""
        self.add_log_message(f"CHYBA: {error_message}")
        self.status_label.setText(f"Chyba: {error_message}")
        self.status_label.setStyleSheet("color: red;")
        self.cancel_button.setText("Zavřít")
        self.cancel_button.setEnabled(True)
    
    @Slot(str)
    def handle_completion(self, output_file: str):
        """Zpracuje úspěšné dokončení"""
        self.add_log_message(f"VRT vrstva úspěšně vytvořena: {output_file}")
        self.status_label.setText(f"VRT vrstva úspěšně vytvořena: {output_file}")
        self.status_label.setStyleSheet("color: green;")
        self.cancel_button.setText("Zavřít")
        self.cancel_button.setEnabled(True)
        
        # Aktualizace progress baru na 100%
        self.progress_bar.setValue(100)