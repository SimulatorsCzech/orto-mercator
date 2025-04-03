from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                             QTableWidget, QTableWidgetItem, QHeaderView, QDialogButtonBox)
from PySide6.QtCore import Qt, QSettings, QObject, Signal
from PySide6.QtGui import QKeySequence, QShortcut, QAction

class KeyboardShortcutsComponent(QObject):
    """Komponenta pro správu klávesových zkratek"""
    
    # Signály
    shortcut_triggered = Signal(str)  # Emitováno při aktivaci zkratky
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.shortcuts = {}
        self.settings = QSettings("OrtoPokrokove", "Aplikace")
        self._load_default_shortcuts()
        self._register_shortcuts()
        
    def _load_default_shortcuts(self):
        """Načte výchozí klávesové zkratky"""
        default_shortcuts = {
            "help": "F1",                    # Nápověda
            "settings": "Ctrl+,",            # Nastavení
            "quit": "Ctrl+Q",                # Ukončit
            "save": "Ctrl+S",                # Uložit
            "open": "Ctrl+O",                # Otevřít
            "export": "Ctrl+E",              # Exportovat
            "next_plugin": "Ctrl+Tab",       # Další plugin
            "prev_plugin": "Ctrl+Shift+Tab", # Předchozí plugin
            "zoom_in": "Ctrl++",             # Přiblížit
            "zoom_out": "Ctrl+-",            # Oddálit
            "zoom_reset": "Ctrl+0",          # Resetovat zoom
            "toggle_theme": "Ctrl+T",        # Přepnout téma
        }
        
        # Načtení uložených zkratek nebo použití výchozích
        self.shortcuts = {}
        for action, default_key in default_shortcuts.items():
            saved_key = self.settings.value(f"shortcuts/{action}", default_key)
            self.shortcuts[action] = saved_key
            
    def _register_shortcuts(self):
        """Zaregistruje klávesové zkratky v aplikaci"""
        # Odstranění existujících zkratek
        if hasattr(self, "_shortcut_objects"):
            for shortcut in self._shortcut_objects:
                shortcut.setEnabled(False)
                shortcut.deleteLater()
                
        # Vytvoření nových zkratek
        self._shortcut_objects = []
        for action, key in self.shortcuts.items():
            if not key:  # Přeskočit prázdné zkratky
                continue
                
            shortcut = QShortcut(QKeySequence(key), self.parent)
            shortcut.activated.connect(lambda a=action: self._shortcut_activated(a))
            self._shortcut_objects.append(shortcut)
            
    def _shortcut_activated(self, action):
        """Zpracuje aktivaci klávesové zkratky"""
        self.shortcut_triggered.emit(action)
        
    def get_shortcut(self, action):
        """Vrátí klávesovou zkratku pro danou akci"""
        return self.shortcuts.get(action, "")
        
    def set_shortcut(self, action, key):
        """Nastaví klávesovou zkratku pro danou akci"""
        self.shortcuts[action] = key
        self.settings.setValue(f"shortcuts/{action}", key)
        self._register_shortcuts()
        
    def show_shortcuts_dialog(self):
        """Zobrazí dialog pro úpravu klávesových zkratek"""
        dialog = ShortcutsDialog(self.parent, self.shortcuts)
        if dialog.exec() == QDialog.Accepted:
            # Uložit změny
            self.shortcuts = dialog.get_shortcuts()
            for action, key in self.shortcuts.items():
                self.settings.setValue(f"shortcuts/{action}", key)
            self._register_shortcuts()
            
    def get_shortcut_descriptions(self):
        """Vrátí popis klávesových zkratek pro nápovědu"""
        descriptions = {
            "help": "Zobrazit nápovědu",
            "settings": "Otevřít nastavení",
            "quit": "Ukončit aplikaci",
            "save": "Uložit projekt",
            "open": "Otevřít projekt",
            "export": "Exportovat výsledky",
            "next_plugin": "Přejít na další plugin",
            "prev_plugin": "Přejít na předchozí plugin",
            "zoom_in": "Přiblížit",
            "zoom_out": "Oddálit",
            "zoom_reset": "Resetovat zoom",
            "toggle_theme": "Přepnout téma",
        }
        
        result = {}
        for action, desc in descriptions.items():
            key = self.shortcuts.get(action, "")
            if key:
                result[action] = {"key": key, "description": desc}
                
        return result
        
class ShortcutsDialog(QDialog):
    """Dialog pro úpravu klávesových zkratek"""
    
    def __init__(self, parent=None, shortcuts=None):
        super().__init__(parent)
        self.shortcuts = shortcuts.copy() if shortcuts else {}
        self._init_ui()
        
    def _init_ui(self):
        # Nastavení dialogu
        self.setWindowTitle("Klávesové zkratky")
        self.resize(500, 400)
        
        # Hlavní layout
        layout = QVBoxLayout(self)
        
        # Tabulka zkratek
        self.shortcuts_table = QTableWidget(len(self.shortcuts), 2)
        self.shortcuts_table.setHorizontalHeaderLabels(["Akce", "Klávesová zkratka"])
        self.shortcuts_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.shortcuts_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.shortcuts_table.verticalHeader().setVisible(False)
        
        # Naplnění tabulky
        self._fill_table()
        
        layout.addWidget(QLabel("Klikněte na zkratku pro její změnu:"))
        layout.addWidget(self.shortcuts_table)
        
        # Tlačítka
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel | QDialogButtonBox.Reset)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        button_box.button(QDialogButtonBox.Reset).clicked.connect(self._reset_shortcuts)
        layout.addWidget(button_box)
        
    def _fill_table(self):
        """Naplní tabulku zkratkami"""
        # Popisky akcí
        descriptions = {
            "help": "Nápověda",
            "settings": "Nastavení",
            "quit": "Ukončit",
            "save": "Uložit",
            "open": "Otevřít",
            "export": "Exportovat",
            "next_plugin": "Další plugin",
            "prev_plugin": "Předchozí plugin",
            "zoom_in": "Přiblížit",
            "zoom_out": "Oddálit",
            "zoom_reset": "Resetovat zoom",
            "toggle_theme": "Přepnout téma",
        }
        
        row = 0
        for action, key in sorted(self.shortcuts.items()):
            # Akce
            action_item = QTableWidgetItem(descriptions.get(action, action))
            action_item.setData(Qt.UserRole, action)
            action_item.setFlags(action_item.flags() & ~Qt.ItemIsEditable)
            
            # Klávesová zkratka
            key_item = QTableWidgetItem(key)
            key_item.setData(Qt.UserRole, key)
            key_item.setFlags(key_item.flags() & ~Qt.ItemIsEditable)
            
            self.shortcuts_table.setItem(row, 0, action_item)
            self.shortcuts_table.setItem(row, 1, key_item)
            row += 1
            
        # Připojení události pro změnu zkratky
        self.shortcuts_table.itemClicked.connect(self._edit_shortcut)
        
    def _edit_shortcut(self, item):
        """Upraví klávesovou zkratku"""
        if item.column() != 1:  # Pouze sloupec se zkratkami
            return
            
        row = item.row()
        action = self.shortcuts_table.item(row, 0).data(Qt.UserRole)
        
        # Vytvoření dialogu pro zadání zkratky
        shortcut_dialog = ShortcutEditDialog(self, action, self.shortcuts[action])
        if shortcut_dialog.exec() == QDialog.Accepted:
            new_key = shortcut_dialog.get_shortcut()
            self.shortcuts[action] = new_key
            item.setText(new_key)
            item.setData(Qt.UserRole, new_key)
            
    def _reset_shortcuts(self):
        """Resetuje zkratky na výchozí hodnoty"""
        default_shortcuts = {
            "help": "F1",
            "settings": "Ctrl+,",
            "quit": "Ctrl+Q",
            "save": "Ctrl+S",
            "open": "Ctrl+O",
            "export": "Ctrl+E",
            "next_plugin": "Ctrl+Tab",
            "prev_plugin": "Ctrl+Shift+Tab",
            "zoom_in": "Ctrl++",
            "zoom_out": "Ctrl+-",
            "zoom_reset": "Ctrl+0",
            "toggle_theme": "Ctrl+T",
        }
        
        self.shortcuts = default_shortcuts.copy()
        self._fill_table()
        
    def get_shortcuts(self):
        """Vrátí upravené zkratky"""
        return self.shortcuts
        
class ShortcutEditDialog(QDialog):
    """Dialog pro zadání klávesové zkratky"""
    
    def __init__(self, parent=None, action="", current_shortcut=""):
        super().__init__(parent)
        self.action = action
        self.current_shortcut = current_shortcut
        self.new_shortcut = ""
        self._init_ui()
        
    def _init_ui(self):
        # Nastavení dialogu
        self.setWindowTitle("Zadejte klávesovou zkratku")
        self.resize(400, 150)
        
        # Hlavní layout
        layout = QVBoxLayout(self)
        
        # Popisek
        layout.addWidget(QLabel(f"Zadejte novou klávesovou zkratku pro akci:"))
        layout.addWidget(QLabel(f"<b>{self.action}</b>"))
        
        # Pole pro zkratku
        self.shortcut_label = QLabel(self.current_shortcut)
        self.shortcut_label.setAlignment(Qt.AlignCenter)
        self.shortcut_label.setStyleSheet("""
            background-color: #f0f0f0;
            border: 1px solid #cccccc;
            border-radius: 4px;
            padding: 8px;
            font-size: 16px;
        """)
        layout.addWidget(self.shortcut_label)
        
        # Instrukce
        layout.addWidget(QLabel("Stiskněte požadovanou kombinaci kláves..."))
        
        # Tlačítka
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        # Nastavení focusu
        self.setFocusPolicy(Qt.StrongFocus)
        self.setFocus()
        
    def keyPressEvent(self, event):
        """Zachytí stisknutí kláves"""
        # Ignorovat samostatné modifikátory
        if event.key() in (Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Meta):
            return
            
        # Vytvořit sekvenci
        key = event.key()
        modifiers = event.modifiers()
        
        sequence = QKeySequence(modifiers | key).toString()
        self.shortcut_label.setText(sequence)
        self.new_shortcut = sequence
        
    def get_shortcut(self):
        """Vrátí novou zkratku nebo původní, pokud nebyla zadána"""
        return self.new_shortcut if self.new_shortcut else self.current_shortcut
