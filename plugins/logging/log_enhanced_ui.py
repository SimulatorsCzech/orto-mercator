"""
Modul obsahující vylepšené uživatelské rozhraní pro zobrazení logů.
"""

from typing import List, Set, Optional, Dict, Any
from datetime import datetime

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QMessageBox,
                              QGroupBox, QPushButton, QTextEdit, QCheckBox, QFileDialog,
                              QGridLayout, QLineEdit, QComboBox, QTabWidget, QSplitter,
                              QTableWidget, QTableWidgetItem, QHeaderView, QMenu,
                              QToolBar, QStatusBar, QMainWindow, QApplication, QStyle)
from PySide6.QtCore import Qt, QTimer, Signal, Slot, QSize
from PySide6.QtGui import (QTextCursor, QColor, QTextCharFormat, QFont, QIcon,
                          QTextDocument, QKeySequence, QAction)

from plugins.logging.log_entry import LogEntry
from plugins.logging.log_manager import LogManager
from plugins.logging.log_search import LogSearch, highlight_search_results
from plugins.logging.log_statistics import LogStatistics
from plugins.logging.log_export import LogExporter
from plugins.logging.log_config import LogConfig

class LogEnhancedUI(QMainWindow):
    """
    Vylepšené uživatelské rozhraní pro zobrazení logů.
    """
    
    def __init__(self, log_manager: LogManager, log_config: LogConfig, parent: QWidget = None):
        """
        Inicializace uživatelského rozhraní.
        
        Args:
            log_manager: Správce logů
            log_config: Konfigurace loggeru
            parent: Rodičovský widget
        """
        super().__init__(parent)
        
        self.log_manager = log_manager
        self.log_config = log_config
        
        # UI komponenty
        self.log_text_edit = None
        self.filter_combo = None
        self.source_combo = None
        self.search_widget = None
        self.status_bar = None
        self.tabs = None
        self.statistics_widget = None
        
        # Aktuální filtr
        self.current_level_filter = "ALL"
        self.current_source_filter = "ALL"
        
        # Vytvoření UI
        self._setup_ui()
        
        # Připojení signálů
        self._connect_signals()
        
        # Nastavení velikosti okna
        self.resize(800, 600)
    
    def _setup_ui(self):
        """
        Vytvoří uživatelské rozhraní.
        """
        # Nastavení titulku okna
        self.setWindowTitle("Logování")
        
        # Vytvoření centrálního widgetu
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        
        # Vytvoření hlavního layoutu
        layout = QVBoxLayout(central_widget)
        
        # Vytvoření záložek
        self.tabs = QTabWidget(self)
        
        # Záložka pro zobrazení logů
        logs_widget = QWidget(self)
        logs_layout = QVBoxLayout(logs_widget)
        
        # Přidání informačního textu
        info = QLabel("Plugin pro podrobné logování celého programu. "
                     "Zaznamenává a zobrazuje podrobné logy o všech operacích v aplikaci.", self)
        info.setWordWrap(True)
        logs_layout.addWidget(info)
        
        # Přidání vyhledávání
        self.search_widget = LogSearch(self)
        self.search_widget.search_changed.connect(self._on_search_changed)
        logs_layout.addWidget(self.search_widget)
        
        # Přidání filtrů
        filters_layout = QHBoxLayout()
        
        # Filtr podle úrovně
        level_label = QLabel("Úroveň:", self)
        self.filter_combo = QComboBox(self)
        self.filter_combo.addItems(["ALL", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        self.filter_combo.setCurrentText(self.log_config.get("log_level", "INFO"))
        self.filter_combo.currentTextChanged.connect(self._on_filter_changed)
        
        filters_layout.addWidget(level_label)
        filters_layout.addWidget(self.filter_combo)
        
        # Filtr podle zdroje
        source_label = QLabel("Zdroj:", self)
        self.source_combo = QComboBox(self)
        self.source_combo.addItem("ALL")
        for source in sorted(self.log_manager.log_sources):
            self.source_combo.addItem(source)
        self.source_combo.currentTextChanged.connect(self._on_filter_changed)
        
        filters_layout.addWidget(source_label)
        filters_layout.addWidget(self.source_combo)
        
        # Checkbox pro automatické scrollování
        self.auto_scroll_checkbox = QCheckBox("Automatické scrollování", self)
        self.auto_scroll_checkbox.setChecked(self.log_config.get("auto_scroll", True))
        filters_layout.addWidget(self.auto_scroll_checkbox)
        
        # Checkbox pro ukládání do souboru
        self.log_to_file_checkbox = QCheckBox("Ukládat do souboru", self)
        self.log_to_file_checkbox.setChecked(self.log_config.get("log_to_file", True))
        self.log_to_file_checkbox.stateChanged.connect(self._on_log_to_file_changed)
        filters_layout.addWidget(self.log_to_file_checkbox)
        
        # Přidáme layout s filtry
        logs_layout.addLayout(filters_layout)
        
        # Textové pole pro zobrazení logů
        self.log_text_edit = QTextEdit(self)
        self.log_text_edit.setReadOnly(True)
        self.log_text_edit.setLineWrapMode(QTextEdit.NoWrap)
        self.log_text_edit.setFont(QFont("Courier New", 9))
        
        # Přidáme kontextové menu
        self.log_text_edit.setContextMenuPolicy(Qt.CustomContextMenu)
        self.log_text_edit.customContextMenuRequested.connect(self._show_context_menu)
        
        logs_layout.addWidget(self.log_text_edit)
        
        # Přidáme záložku s logy
        self.tabs.addTab(logs_widget, "Logy")
        
        # Záložka pro statistiky
        self.statistics_widget = LogStatistics(self.log_manager, self)
        self.tabs.addTab(self.statistics_widget, "Statistiky")
        
        # Přidáme záložky do hlavního layoutu
        layout.addWidget(self.tabs)
        
        # Vytvoření toolbaru
        self._create_toolbar()
        
        # Vytvoření status baru
        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Připraven")
        
        # Inicializace zobrazení logů
        self._update_log_display()
    
    def _create_toolbar(self):
        """
        Vytvoří toolbar s akcemi.
        """
        # Vytvoření toolbaru
        toolbar = QToolBar("Nástroje", self)
        toolbar.setIconSize(QSize(16, 16))
        self.addToolBar(toolbar)
        
        # Akce pro vyčištění logů
        clear_action = QAction(self.style().standardIcon(QStyle.SP_DialogResetButton), "Vyčistit", self)
        clear_action.setStatusTip("Vyčistit všechny logy")
        clear_action.triggered.connect(self._on_clear_clicked)
        toolbar.addAction(clear_action)
        
        # Akce pro uložení logů
        save_action = QAction(self.style().standardIcon(QStyle.SP_DialogSaveButton), "Uložit", self)
        save_action.setStatusTip("Uložit logy do souboru")
        save_action.triggered.connect(self._on_save_clicked)
        toolbar.addAction(save_action)
        
        # Oddělovač
        toolbar.addSeparator()
        
        # Akce pro export do CSV
        export_csv_action = QAction("Export CSV", self)
        export_csv_action.setStatusTip("Exportovat logy do CSV souboru")
        export_csv_action.triggered.connect(lambda: self._on_export_clicked("csv"))
        toolbar.addAction(export_csv_action)
        
        # Akce pro export do HTML
        export_html_action = QAction("Export HTML", self)
        export_html_action.setStatusTip("Exportovat logy do HTML souboru")
        export_html_action.triggered.connect(lambda: self._on_export_clicked("html"))
        toolbar.addAction(export_html_action)
        
        # Akce pro export do JSON
        export_json_action = QAction("Export JSON", self)
        export_json_action.setStatusTip("Exportovat logy do JSON souboru")
        export_json_action.triggered.connect(lambda: self._on_export_clicked("json"))
        toolbar.addAction(export_json_action)
        
        # Oddělovač
        toolbar.addSeparator()
        
        # Akce pro obnovení
        refresh_action = QAction(self.style().standardIcon(QStyle.SP_BrowserReload), "Obnovit", self)
        refresh_action.setStatusTip("Obnovit zobrazení logů")
        refresh_action.triggered.connect(self._update_log_display)
        toolbar.addAction(refresh_action)
    
    def _connect_signals(self):
        """
        Připoj�� signály k příslušným slotům.
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
        
        # Aktualizujeme status bar
        self.status_bar.showMessage(f"Přidán nový log: {log_entry.level} - {log_entry.message}")
    
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
    
    def _on_search_changed(self, search_text: str, case_sensitive: bool, whole_word: bool):
        """
        Slot volaný při změně vyhledávání.
        
        Args:
            search_text: Text vyhledávání
            case_sensitive: Zda se má rozlišovat velikost písmen
            whole_word: Zda se mají hledat pouze celá slova
        """
        # Zvýrazníme výsledky vyhledávání
        count = highlight_search_results(self.log_text_edit.document(), search_text, case_sensitive, whole_word)
        
        # Aktualizujeme status bar
        if search_text:
            self.status_bar.showMessage(f"Nalezeno {count} výskytů")
        else:
            self.status_bar.showMessage("Vyhledávání vyčištěno")
    
    def _on_clear_clicked(self):
        """
        Slot volaný při kliknutí na tlačítko 'Vyčistit'.
        """
        # Vyčistíme logy
        self.log_manager.clear_logs()
        
        # Vyčistíme textové pole
        self.log_text_edit.clear()
        
        # Aktualizujeme status bar
        self.status_bar.showMessage("Logy byly vyčištěny")
    
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
            self.status_bar.showMessage(f"Logy byly uloženy do souboru: {file_path}")
        else:
            # Zobrazíme chybu
            QMessageBox.critical(self, "Chyba p��i ukládání", f"Nepodařilo se uložit logy do souboru:\n{file_path}")
            self.status_bar.showMessage("Chyba při ukládání logů")
    
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
            self.status_bar.showMessage(f"Logy byly exportovány do souboru: {file_path}")
        else:
            # Zobrazíme chybu
            QMessageBox.critical(self, "Chyba při exportu", f"Nepodařilo se exportovat logy do souboru:\n{file_path}")
            self.status_bar.showMessage("Chyba při exportu logů")
    
    def _on_log_to_file_changed(self, state: bool):
        """
        Slot volaný při změně stavu checkboxu pro ukládání do souboru.
        
        Args:
            state: Nový stav checkboxu
        """
        # Nastavíme ukládání do souboru
        self.log_manager.set_log_to_file(state)
        
        # Aktualizujeme konfiguraci
        self.log_config.set("log_to_file", state)
        self.log_config.save_config()
    
    def _show_context_menu(self, position):
        """
        Zobrazí kontextové menu pro textové pole s logy.
        
        Args:
            position: Pozice kurzoru
        """
        # Vytvoříme kontextové menu
        menu = QMenu(self)
        
        # Přidáme akce
        copy_action = menu.addAction("Kopírovat")
        copy_action.triggered.connect(self.log_text_edit.copy)
        
        select_all_action = menu.addAction("Vybrat vše")
        select_all_action.triggered.connect(self.log_text_edit.selectAll)
        
        menu.addSeparator()
        
        clear_action = menu.addAction("Vyčistit")
        clear_action.triggered.connect(self._on_clear_clicked)
        
        save_action = menu.addAction("Uložit")
        save_action.triggered.connect(self._on_save_clicked)
        
        # Zobrazíme menu
        menu.exec_(self.log_text_edit.mapToGlobal(position))
    
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
        
        # Aktualizujeme status bar
        self.status_bar.showMessage(f"Zobrazeno {len(filtered_logs)} logů")
        
        # Pokud máme aktivní vyhledávání, zvýrazníme výsledky
        if hasattr(self, 'search_widget') and self.search_widget:
            search_text = self.search_widget.current_search
            if search_text:
                case_sensitive = self.search_widget.case_sensitive
                whole_word = self.search_widget.whole_word
                count = highlight_search_results(self.log_text_edit.document(), search_text, case_sensitive, whole_word)
                self.status_bar.showMessage(f"Zobrazeno {len(filtered_logs)} logů, nalezeno {count} výskytů")
    
    def closeEvent(self, event):
        """
        Metoda volaná při zavření okna.
        
        Args:
            event: Událost zavření
        """
        # Uložíme konfiguraci
        self.log_config.set("log_level", self.current_level_filter)
        self.log_config.set("auto_scroll", self.auto_scroll_checkbox.isChecked())
        self.log_config.save_config()
        
        # Pokračujeme v události
        super().closeEvent(event)