from PySide6.QtWidgets import (QWidget, QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QTabWidget, QCheckBox, QComboBox, 
                             QSpinBox, QLineEdit, QGroupBox, QFormLayout, QDialogButtonBox)
from PySide6.QtCore import Qt, Signal, QSettings, QObject
from PySide6.QtGui import QFont, QIcon

class SettingsComponent(QObject):
    """Komponenta pro správu nastavení aplikace"""
    
    # Signály
    settings_changed = Signal(dict)  # Emitováno při změně nastavení
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.settings = QSettings("OrtoPokrokove", "Aplikace")
        self._load_default_settings()
        
    def _load_default_settings(self):
        """Načte výchozí nastavení, pokud neexistují"""
        # Obecná nastavení
        if not self.settings.contains("general/language"):
            self.settings.setValue("general/language", "cs")
        if not self.settings.contains("general/theme"):
            self.settings.setValue("general/theme", "light")
        if not self.settings.contains("general/autosave"):
            self.settings.setValue("general/autosave", True)
        if not self.settings.contains("general/autosave_interval"):
            self.settings.setValue("general/autosave_interval", 5)  # minuty
        if not self.settings.contains("general/confirm_exit"):
            self.settings.setValue("general/confirm_exit", True)
            
        # Nastavení exportu
        if not self.settings.contains("export/default_format"):
            self.settings.setValue("export/default_format", "png")
        if not self.settings.contains("export/default_quality"):
            self.settings.setValue("export/default_quality", 90)
        if not self.settings.contains("export/default_path"):
            self.settings.setValue("export/default_path", "")
            
        # Nastavení pluginů
        if not self.settings.contains("plugins/autoload"):
            self.settings.setValue("plugins/autoload", True)
            
    def get_setting(self, key, default=None, value_type=None):
        """Získá hodnotu nastavení
        
        Args:
            key: Klíč nastavení
            default: Výchozí hodnota, pokud nastavení neexistuje
            value_type: Typ hodnoty (bool, int, str, atd.)
        """
        if value_type is not None:
            return self.settings.value(key, default, type=value_type)
        return self.settings.value(key, default)
        
    def set_setting(self, key, value):
        """Nastaví hodnotu nastavení"""
        self.settings.setValue(key, value)
        
        # Emitovat signál o změně nastavení
        changed_settings = {key: value}
        self.settings_changed.emit(changed_settings)
        
    def show_settings_dialog(self):
        """Zobrazí dialog nastavení"""
        dialog = SettingsDialog(self.parent, self.settings)
        if dialog.exec() == QDialog.Accepted:
            # Uložit změny a emitovat signál
            changed_settings = dialog.get_changed_settings()
            if changed_settings:
                self.settings_changed.emit(changed_settings)
                
class SettingsDialog(QDialog):
    """Dialog pro úpravu nastavení aplikace"""
    
    def __init__(self, parent=None, settings=None):
        super().__init__(parent)
        self.settings = settings
        self.changed_settings = {}
        self._init_ui()
        
    def _init_ui(self):
        # Nastavení dialogu
        self.setWindowTitle("Nastavení aplikace")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)
        
        # Hlavní layout
        layout = QVBoxLayout(self)
        
        # Záložky nastavení
        self.tab_widget = QTabWidget()
        
        # Záložka obecných nastavení
        general_tab = QWidget()
        general_layout = QVBoxLayout(general_tab)
        
        # Skupina pro jazyk a vzhled
        appearance_group = QGroupBox("Vzhled a jazyk")
        appearance_layout = QFormLayout(appearance_group)
        
        # Výběr jazyka
        self.language_combo = QComboBox()
        self.language_combo.addItem("Čeština", "cs")
        self.language_combo.addItem("English", "en")
        current_lang = self.settings.value("general/language", "cs")
        self.language_combo.setCurrentIndex(0 if current_lang == "cs" else 1)
        appearance_layout.addRow("Jazyk:", self.language_combo)
        
        # Výběr tématu
        self.theme_combo = QComboBox()
        self.theme_combo.addItem("Světlé téma", "light")
        self.theme_combo.addItem("Tmavé téma", "dark")
        self.theme_combo.addItem("Systémové téma", "system")
        current_theme = self.settings.value("general/theme", "light")
        self.theme_combo.setCurrentIndex(0 if current_theme == "light" else 1 if current_theme == "dark" else 2)
        appearance_layout.addRow("Téma:", self.theme_combo)
        
        general_layout.addWidget(appearance_group)
        
        # Skupina pro automatické ukládání
        autosave_group = QGroupBox("Automatické ukládání")
        autosave_layout = QFormLayout(autosave_group)
        
        # Zapnutí automatického ukládání
        self.autosave_check = QCheckBox()
        self.autosave_check.setChecked(self.settings.value("general/autosave", True, type=bool))
        autosave_layout.addRow("Povolit automatické ukládání:", self.autosave_check)
        
        # Interval automatického ukládání
        self.autosave_interval = QSpinBox()
        self.autosave_interval.setRange(1, 60)
        self.autosave_interval.setValue(self.settings.value("general/autosave_interval", 5, type=int))
        self.autosave_interval.setSuffix(" min")
        autosave_layout.addRow("Interval ukládání:", self.autosave_interval)
        
        general_layout.addWidget(autosave_group)
        general_layout.addStretch(1)
        
        # Záložka nastavení exportu
        export_tab = QWidget()
        export_layout = QVBoxLayout(export_tab)
        
        # Skupina pro export
        export_group = QGroupBox("Nastavení exportu")
        export_form = QFormLayout(export_group)
        
        # Výchozí formát
        self.export_format = QComboBox()
        self.export_format.addItem("PNG (.png)", "png")
        self.export_format.addItem("JPEG (.jpg)", "jpg")
        self.export_format.addItem("TIFF (.tiff)", "tiff")
        current_format = self.settings.value("export/default_format", "png")
        self.export_format.setCurrentIndex(0 if current_format == "png" else 1 if current_format == "jpg" else 2)
        export_form.addRow("Výchozí formát:", self.export_format)
        
        # Kvalita exportu
        self.export_quality = QSpinBox()
        self.export_quality.setRange(1, 100)
        self.export_quality.setValue(self.settings.value("export/default_quality", 90, type=int))
        self.export_quality.setSuffix(" %")
        export_form.addRow("Kvalita exportu:", self.export_quality)
        
        # Výchozí cesta
        self.export_path = QLineEdit()
        self.export_path.setText(self.settings.value("export/default_path", ""))
        self.export_path.setPlaceholderText("Výchozí složka pro export")
        export_form.addRow("Výchozí cesta:", self.export_path)
        
        export_layout.addWidget(export_group)
        export_layout.addStretch(1)
        
        # Přidání záložek
        self.tab_widget.addTab(general_tab, "Obecné")
        self.tab_widget.addTab(export_tab, "Export")
        
        layout.addWidget(self.tab_widget)
        
        # Tlačítka
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self._save_settings)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
    def _save_settings(self):
        """Uloží změněná nastavení"""
        # Obecná nastavení
        new_lang = self.language_combo.currentData()
        if new_lang != self.settings.value("general/language"):
            self.settings.setValue("general/language", new_lang)
            self.changed_settings["general/language"] = new_lang
            
        new_theme = self.theme_combo.currentData()
        if new_theme != self.settings.value("general/theme"):
            self.settings.setValue("general/theme", new_theme)
            self.changed_settings["general/theme"] = new_theme
            
        new_autosave = self.autosave_check.isChecked()
        if new_autosave != self.settings.value("general/autosave", True, type=bool):
            self.settings.setValue("general/autosave", new_autosave)
            self.changed_settings["general/autosave"] = new_autosave
            
        new_interval = self.autosave_interval.value()
        if new_interval != self.settings.value("general/autosave_interval", 5, type=int):
            self.settings.setValue("general/autosave_interval", new_interval)
            self.changed_settings["general/autosave_interval"] = new_interval
            
        # Nastavení exportu
        new_format = self.export_format.currentData()
        if new_format != self.settings.value("export/default_format"):
            self.settings.setValue("export/default_format", new_format)
            self.changed_settings["export/default_format"] = new_format
            
        new_quality = self.export_quality.value()
        if new_quality != self.settings.value("export/default_quality", 90, type=int):
            self.settings.setValue("export/default_quality", new_quality)
            self.changed_settings["export/default_quality"] = new_quality
            
        new_path = self.export_path.text()
        if new_path != self.settings.value("export/default_path", ""):
            self.settings.setValue("export/default_path", new_path)
            self.changed_settings["export/default_path"] = new_path
            
        self.accept()
        
    def get_changed_settings(self):
        """Vrátí slovník změněných nastavení"""
        return self.changed_settings
