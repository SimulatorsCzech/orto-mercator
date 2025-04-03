"""
Modul obsahující komponentu pro vyhledávání v logech.
"""

from typing import List, Optional

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                              QPushButton, QLineEdit, QCheckBox)
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QTextCursor, QTextCharFormat, QColor, QTextDocument

from plugins.logging.log_entry import LogEntry

class LogSearch(QWidget):
    """
    Komponenta pro vyhledávání v logech.
    """
    
    # Signál pro oznámení, že se změnilo vyhledávání
    search_changed = Signal(str, bool, bool)
    
    def __init__(self, parent: QWidget = None):
        """
        Inicializace komponenty pro vyhledávání.
        
        Args:
            parent: Rodičovský widget
        """
        super().__init__(parent)
        
        # UI komponenty
        self.search_input = None
        self.case_sensitive_checkbox = None
        self.whole_word_checkbox = None
        self.next_button = None
        self.prev_button = None
        self.clear_button = None
        
        # Aktuální vyhledávání
        self.current_search = ""
        self.case_sensitive = False
        self.whole_word = False
        
        # Vytvoření UI
        self._setup_ui()
    
    def _setup_ui(self):
        """
        Vytvoří uživatelské rozhraní.
        """
        # Vytvoření hlavního layoutu
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Přidání popisku
        label = QLabel("Hledat:", self)
        layout.addWidget(label)
        
        # Přidání vstupního pole
        self.search_input = QLineEdit(self)
        self.search_input.setPlaceholderText("Zadejte hledaný text...")
        self.search_input.textChanged.connect(self._on_search_text_changed)
        self.search_input.returnPressed.connect(self._on_search_next)
        layout.addWidget(self.search_input)
        
        # Přidání checkboxů
        self.case_sensitive_checkbox = QCheckBox("Rozlišovat velikost", self)
        self.case_sensitive_checkbox.stateChanged.connect(self._on_search_options_changed)
        layout.addWidget(self.case_sensitive_checkbox)
        
        self.whole_word_checkbox = QCheckBox("Celá slova", self)
        self.whole_word_checkbox.stateChanged.connect(self._on_search_options_changed)
        layout.addWidget(self.whole_word_checkbox)
        
        # Přidání tlačítek
        self.prev_button = QPushButton("Předchozí", self)
        self.prev_button.clicked.connect(self._on_search_prev)
        layout.addWidget(self.prev_button)
        
        self.next_button = QPushButton("Další", self)
        self.next_button.clicked.connect(self._on_search_next)
        layout.addWidget(self.next_button)
        
        self.clear_button = QPushButton("Vyčistit", self)
        self.clear_button.clicked.connect(self._on_clear_search)
        layout.addWidget(self.clear_button)
        
        # Nastavíme výchozí stav tlačítek
        self._update_button_state()
    
    def _on_search_text_changed(self, text: str):
        """
        Slot volaný při změně textu vyhledávání.
        
        Args:
            text: Nový text vyhledávání
        """
        self.current_search = text
        self._update_button_state()
        self.search_changed.emit(text, self.case_sensitive, self.whole_word)
    
    def _on_search_options_changed(self):
        """
        Slot volaný při změně možností vyhledávání.
        """
        self.case_sensitive = self.case_sensitive_checkbox.isChecked()
        self.whole_word = self.whole_word_checkbox.isChecked()
        self.search_changed.emit(self.current_search, self.case_sensitive, self.whole_word)
    
    def _on_search_next(self):
        """
        Slot volaný při kliknutí na tlačítko 'Další'.
        """
        # Emitujeme signál pro vyhledání dalšího výskytu
        self.search_changed.emit(self.current_search, self.case_sensitive, self.whole_word)
    
    def _on_search_prev(self):
        """
        Slot volaný při kliknutí na tlačítko 'Předchozí'.
        """
        # Emitujeme signál pro vyhledání předchozího výskytu
        self.search_changed.emit(self.current_search, self.case_sensitive, self.whole_word)
    
    def _on_clear_search(self):
        """
        Slot volaný při kliknutí na tlačítko 'Vyčistit'.
        """
        self.search_input.clear()
        self.case_sensitive_checkbox.setChecked(False)
        self.whole_word_checkbox.setChecked(False)
        self.search_changed.emit("", False, False)
    
    def _update_button_state(self):
        """
        Aktualizuje stav tlačítek podle aktuálního vyhledávání.
        """
        enabled = bool(self.current_search)
        self.next_button.setEnabled(enabled)
        self.prev_button.setEnabled(enabled)
        self.clear_button.setEnabled(enabled)

def highlight_search_results(document: QTextDocument, search_text: str, 
                            case_sensitive: bool = False, whole_word: bool = False) -> int:
    """
    Zvýrazní výsledky vyhledávání v dokumentu.
    
    Args:
        document: Dokument, ve kterém se má vyhledávat
        search_text: Hledaný text
        case_sensitive: Zda se má rozlišovat velikost písmen
        whole_word: Zda se mají hledat pouze celá slova
        
    Returns:
        Počet nalezených výskytů
    """
    if not search_text:
        return 0
    
    # Nastavíme možnosti vyhledávání
    options = QTextDocument.FindFlags()
    if case_sensitive:
        options |= QTextDocument.FindCaseSensitively
    if whole_word:
        options |= QTextDocument.FindWholeWords
    
    # Vytvoříme formát pro zvýraznění
    highlight_format = QTextCharFormat()
    highlight_format.setBackground(QColor(255, 255, 0, 100))  # Žluté pozadí s průhledností
    
    # Hledáme všechny výskyty
    cursor = QTextCursor(document)
    count = 0
    
    # Resetujeme formátování
    cursor.select(QTextCursor.Document)
    cursor.setCharFormat(QTextCharFormat())
    cursor.clearSelection()
    
    # Hledáme a zvýrazňujeme
    cursor = document.find(search_text, 0, options)
    while not cursor.isNull():
        cursor.mergeCharFormat(highlight_format)
        cursor = document.find(search_text, cursor, options)
        count += 1
    
    return count