"""
Modul obsahující komponenty uživatelského rozhraní pro zobrazení logů.
"""

import os
from datetime import datetime
from typing import List, Set, Optional

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QMessageBox,
                              QGroupBox, QPushButton, QTextEdit, QCheckBox, QFileDialog,
                              QGridLayout, QLineEdit, QComboBox, QTabWidget, QSplitter,
                              QToolBar, QStatusBar, QMainWindow)
from PySide6.QtCore import Qt, QTimer, Signal, Slot, QSize
from PySide6.QtGui import QTextCursor, QColor, QTextCharFormat, QFont, QAction, QIcon

from plugins.logging.log_entry import LogEntry
from plugins.logging.log_manager import LogManager
from plugins.logging.log_config import LogConfig
from plugins.logging.log_export import LogExporter

class LoggingUI(QWidget):
    """
    Třída pro uživatelské rozhraní loggeru.
    """
    
    def __init__(self, log_manager: LogManager, config: LogConfig = None, parent: QWidget = None):
        """
        Inicializace uživatelského rozhraní.
        
        Args:
            log_manager: Správce logů
            config: Konfigurace loggeru (pokud není zadána, použije se konfigurace z log_manager)
            parent: Rodičovský widget
        """
        super().__init__(parent)
        
        self.log_manager = log_manager
        self.config = config.get_all() if config else log_manager.config
        
        # UI komponenty
        self.log_text_edit = None
        self.filter_combo = None
        self.source_combo = None
        self.clear_button = None
        self.save_button = None
        self.auto_scroll_checkbox = None
        self.log_to_file_checkbox = None
        self.search_edit = None
        self.status_label = None
        
        # Aktuální filtr
        self.current_level_filter = "ALL"
        self.current_source_filter = "ALL"
        self.current_search_text = ""
        
        # Vytvoření UI
        self._setup_ui()
        
        # Připojení signálů
        self._connect_signals()
    
    def _setup_ui(self):
        """
        Vytvoří uživatelské rozhraní.
        """
        # Vytvoření hlavního layoutu
        layout = QVBoxLayout(self)
        
        # Přidání titulku
        title = QLabel("<h2>Logování</h2>", self)
        layout.addWidget(title)
        
        # Přidání informačního textu
        info = QLabel("Plugin pro podrobné logování celého programu. "
                     "Zaznamenává a zobrazuje podrobné logy o všech operacích v aplikaci.", self)
        info.setWordWrap(True)
        layout.addWidget(info)
        
        # Horní panel s filtry a vyhledáváním
        top_panel = QHBoxLayout()
        
        # Filtr podle úrovně
        level_label = QLabel("Úroveň:", self)
        self.filter_combo = QComboBox(self)
        self.filter_combo.addItems(["ALL", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        self.filter_combo.setCurrentText(self.config.get("log_level", "INFO"))
        self.filter_combo.currentTextChanged.connect(self._on_filter_changed)
        
        top_panel.addWidget(level_label)
        top_panel.addWidget(self.filter_combo)
        
        # Filtr podle zdroje
        source_label = QLabel("Zdroj:", self)
        self.source_combo = QComboBox(self)
        self.source_combo.addItem("ALL")
        for source in sorted(self.log_manager.log_sources):
            self.source_combo.addItem(source)
        self.source_combo.currentTextChanged.connect(self._on_filter_changed)
        
        top_panel.addWidget(source_label)
        top_panel.addWidget(self.source_combo)
        
        # Vyhledávání
        search_label = QLabel("Hledat:", self)
        self.search_edit = QLineEdit(self)
        self.search_edit.setPlaceholderText("Zadejte text pro vyhledávání...")
        self.search_edit.textChanged.connect(self._on_search_changed)
        
        top_panel.addWidget(search_label)
        top_panel.addWidget(self.search_edit)
        
        layout.addLayout(top_panel)
        
        # Nastavení
        settings_layout = QHBoxLayout()
        
        # Checkbox pro automatické scrollování
        self.auto_scroll_checkbox = QCheckBox("Automatické scrollování", self)
        self.auto_scroll_checkbox.setChecked(self.config.get("auto_scroll", True))
        settings_layout.addWidget(self.auto_scroll_checkbox)
        
        # Checkbox pro ukládání do souboru
        self.log_to_file_checkbox = QCheckBox("Ukládat do souboru", self)
        self.log_to_file_checkbox.setChecked(self.config.get("log_to_file", True))
        self.log_to_file_checkbox.stateChanged.connect(self._on_log_to_file_changed)
        settings_layout.addWidget(self.log_to_file_checkbox)
        
        # Přidáme informaci o souboru
        log_file_label = QLabel(f"Soubor: {self.config.get('log_file', '')}", self)
        settings_layout.addWidget(log_file_label)
        
        # Přidáme stretch, aby se komponenty zarovnaly doleva
        settings_layout.addStretch()
        
        layout.addLayout(settings_layout)
        
        # Textové pole pro zobrazení logů
        self.log_text_edit = QTextEdit(self)
        self.log_text_edit.setReadOnly(True)
        self.log_text_edit.setLineWrapMode(QTextEdit.NoWrap)
        self.log_text_edit.setFont(QFont("Courier New", 9))
        layout.addWidget(self.log_text_edit)
        
        # Tlačítka
        buttons_layout = QHBoxLayout()
        
        self.clear_button = QPushButton("Vyčistit", self)
        self.clear_button.clicked.connect(self._on_clear_clicked)
        buttons_layout.addWidget(self.clear_button)
        
        self.save_button = QPushButton("Uložit", self)
        self.save_button.clicked.connect(self._on_save_clicked)
        buttons_layout.addWidget(self.save_button)
        
        # Tlačítka pro export
        export_csv_button = QPushButton("Export CSV", self)
        export_csv_button.clicked.connect(lambda: self._on_export_clicked("csv"))
        buttons_layout.addWidget(export_csv_button)
        
        export_html_button = QPushButton("Export HTML", self)
        export_html_button.clicked.connect(lambda: self._on_export_clicked("html"))
        buttons_layout.addWidget(export_html_button)
        
        export_json_button = QPushButton("Export JSON", self)
        export_json_button.clicked.connect(lambda: self._on_export_clicked("json"))
        buttons_layout.addWidget(export_json_button)
        
        # Přidáme stretch, aby se tlačítka zarovnala doleva
        buttons_layout.addStretch()
        
        layout.addLayout(buttons_layout)
        
        # Stavový řádek
        self.status_label = QLabel("Připraven", self)
        layout.addWidget(self.status_label)
        
        # Inicializace zobrazení logů
        self._update_log_display()
    
    def _connect_signals(self):
        """
        Připojí signály k příslušným slotům.
        """
        # Připojení signálu pro přidání nového logu
        self.log_manager.log_added.connect(self._on_log_added)
        
        # Připojení signálu pro změnu seznamu zdrojů
        self.log_manager.sources_changed.connect(self._on_sources_changed)
    
    def _on_log_added(self, log_entry: LogEntry):
        """
        Slot volaný při přidání nového logu.
        
        Args:
            log_entry: Nový záznam logu
        """
        # Aktualizujeme zobrazení logů
        self._update_log_display()
        
        # Aktualizujeme status
        self.status_label.setText(f"Přidán nový log: {log_entry.level} - {log_entry.message}")
    
    def _on_sources_changed(self, sources: Set[str]):
        """
        Slot volaný při změně seznamu zdrojů.
        
        Args:
            sources: Nový seznam zdrojů
        """
        # Aktualizujeme seznam zdrojů v comboboxu
        current_source = self.source_combo.currentText()
        
        # Vyčistíme combobox
        self.source_combo.clear()
        
        # Přidáme položku "ALL"
        self.source_combo.addItem("ALL")
        
        # Přidáme všechny zdroje
        for source in sorted(sources):
            self.source_combo.addItem(source)
        
        # Nastavíme původní výběr, pokud existuje
        index = self.source_combo.findText(current_source)
        if index >= 0:
            self.source_combo.setCurrentIndex(index)
    
    def _on_filter_changed(self):
        """
        Slot volaný při změně filtru úrovně nebo zdroje.
        """
        # Aktualizujeme aktuální filtr
        self.current_level_filter = self.filter_combo.currentText()
        self.current_source_filter = self.source_combo.currentText()
        
        # Aktualizujeme zobrazení logů
        self._update_log_display()
    
    def _on_search_changed(self, text: str):
        """
        Slot volaný při změně textu vyhledávání.
        
        Args:
            text: Nový text vyhledávání
        """
        # Aktualizujeme aktuální text vyhledávání
        self.current_search_text = text
        
        # Aktualizujeme zobrazení logů
        self._update_log_display()
    
    def _on_clear_clicked(self):
        """
        Slot volaný při kliknutí na tlačítko 'Vyčistit'.
        """
        # Vyčistíme logy
        self.log_manager.clear_logs()
        
        # Vyčistíme textové pole
        self.log_text_edit.clear()
        
        # Aktualizujeme status
        self.status_label.setText("Logy byly vyčištěny")
    
    def _on_save_clicked(self):
        """
        Slot volaný při kliknutí na tlačítko 'Uložit'.
        """
        # Otevřeme dialog pro výběr souboru
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Uložit logy",
            f"ortofoto_app_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log",
            "Log soubory (*.log);;Textové soubory (*.txt);;Všechny soubory (*.*)"
        )
        
        if not file_path:
            return
        
        # Uložíme logy do souboru
        if self.log_manager.save_logs_to_file(file_path):
            # Zobrazíme informaci o úspěšném uložení
            QMessageBox.information(self, "Logy uloženy", f"Logy byly úspěšně uloženy do souboru:\n{file_path}")
            self.status_label.setText(f"Logy byly uloženy do souboru: {file_path}")
        else:
            # Zobrazíme chybu
            QMessageBox.critical(self, "Chyba při ukládání", f"Nepodařilo se uložit logy do souboru:\n{file_path}")
            self.status_label.setText("Chyba při ukládání logů")
    
    def _on_export_clicked(self, format_type: str):
        """
        Slot volaný při kliknutí na tlačítko pro export.
        
        Args:
            format_type: Typ formátu pro export (csv, html, json)
        """
        # Otevřeme dialog pro výběr souboru
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            f"Exportovat logy do {format_type.upper()}",
            f"ortofoto_app_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{format_type}",
            f"{format_type.upper()} soubory (*.{format_type});;Všechny soubory (*.*)"
        )
        
        if not file_path:
            return
        
        # Získáme filtrované logy
        logs = self.log_manager.get_filtered_logs(self.current_level_filter, self.current_source_filter)
        
        # Exportujeme logy
        if LogExporter.export(logs, file_path):
            # Zobrazíme informaci o úspěšném exportu
            QMessageBox.information(self, "Logy exportovány", f"Logy byly úspěšně exportovány do souboru:\n{file_path}")
            self.status_label.setText(f"Logy byly exportovány do souboru: {file_path}")
        else:
            # Zobrazíme chybu
            QMessageBox.critical(self, "Chyba při exportu", f"Nepodařilo se exportovat logy do souboru:\n{file_path}")
            self.status_label.setText("Chyba při exportu logů")
    
    def _on_log_to_file_changed(self, state: bool):
        """
        Slot volaný při změně stavu checkboxu pro ukládání do souboru.
        
        Args:
            state: Nový stav checkboxu
        """
        # Nastavíme ukládání do souboru
        self.log_manager.set_log_to_file(state)
        
        # Aktualizujeme status
        if state:
            self.status_label.setText(f"Ukládání logů do souboru zapnuto: {self.config.get('log_file', '')}")
        else:
            self.status_label.setText("Ukládání logů do souboru vypnuto")
    
    def _highlight_search_results(self, text: str):
        """
        Zvýrazní výsledky vyhledávání v textovém poli.
        
        Args:
            text: Text pro vyhledávání
        """
        if not text:
            return
        
        # Vytvoříme kurzor pro vyhledávání
        cursor = self.log_text_edit.textCursor()
        cursor.movePosition(QTextCursor.Start)
        
        # Formát pro zvýraznění
        highlight_format = QTextCharFormat()
        highlight_format.setBackground(QColor(255, 255, 0))  # Žlutá
        
        # Počítadlo nalezených výskytů
        count = 0
        
        # Hledáme všechny výskyty
        while True:
            # Hledáme další výskyt
            cursor = self.log_text_edit.document().find(text, cursor)
            
            # Pokud jsme nenašli další výskyt, končíme
            if cursor.isNull():
                break
            
            # Zvýrazníme nalezený text
            cursor.mergeCharFormat(highlight_format)
            
            # Zvýšíme počítadlo
            count += 1
        
        # Aktualizujeme status
        if count > 0:
            self.status_label.setText(f"Nalezeno {count} výskytů")
        else:
            self.status_label.setText("Žádné výskyty nenalezeny")
    
    def _update_log_display(self):
        """
        Aktualizuje zobrazení logů v UI.
        Filtruje logy podle vybrané úrovně a zdroje.
        """
        if not self.log_text_edit:
            return
        
        # Získáme vybranou úroveň a zdroj
        selected_level = self.current_level_filter
        selected_source = self.current_source_filter
        
        # Uložíme aktuální pozici kurzoru
        cursor = self.log_text_edit.textCursor()
        cursor_position = cursor.position()
        
        # Vyčistíme textové pole
        self.log_text_edit.clear()
        
        # Nastavíme formát textu
        cursor = self.log_text_edit.textCursor()
        
        # Získáme filtrované logy
        filtered_logs = self.log_manager.get_filtered_logs(selected_level, selected_source)
        
        # Filtrujeme podle vyhledávání
        if self.current_search_text:
            filtered_logs = [log for log in filtered_logs if self.current_search_text.lower() in str(log).lower()]
        
        # Zobrazujeme logy
        for entry in filtered_logs:
            # Nastavíme barvu podle úrovně
            format = QTextCharFormat()
            format.setForeground(entry.get_color())
            
            # Přidáme záznam do textového pole
            cursor.insertText(str(entry) + "\n", format)
        
        # Nastavíme kurzor na konec, pokud je zapnutý auto-scroll
        if self.auto_scroll_checkbox and self.auto_scroll_checkbox.isChecked():
            cursor.movePosition(QTextCursor.End)
            self.log_text_edit.setTextCursor(cursor)
        else:
            # Jinak se pokusíme obnovit původní pozici
            cursor.setPosition(min(cursor_position, len(self.log_text_edit.toPlainText())))
            self.log_text_edit.setTextCursor(cursor)
        
        # Zvýrazníme výsledky vyhledávání
        if self.current_search_text:
            self._highlight_search_results(self.current_search_text)
        
        # Aktualizujeme status
        self.status_label.setText(f"Zobrazeno {len(filtered_logs)} logů")
    
    def update_config(self, config: dict):
        """
        Aktualizuje konfiguraci UI.
        
        Args:
            config: Nová konfigurace
        """
        self.config = config
        
        # Aktualizujeme UI podle nové konfigurace
        if self.auto_scroll_checkbox:
            self.auto_scroll_checkbox.setChecked(config.get("auto_scroll", True))
        
        if self.log_to_file_checkbox:
            self.log_to_file_checkbox.setChecked(config.get("log_to_file", True))
        
        if self.filter_combo:
            self.filter_combo.setCurrentText(config.get("log_level", "INFO"))
        
        # Aktualizujeme zobrazení logů
        self._update_log_display()