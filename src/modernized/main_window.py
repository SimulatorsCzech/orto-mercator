import os
import sys
from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QSplitter, QMessageBox
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction  # Přidáno QAction pro případné použití

from .components.toolbar import ToolbarComponent
from .components.plugin_panel import PluginPanelComponent
from .components.content_panel import ContentPanelComponent
from .components.theme_manager import ThemeManager
from .components.status_panel import StatusPanelComponent
from .components.notification import NotificationComponent
from .components.settings import SettingsComponent
from .components.help import HelpComponent
from .components.keyboard_shortcuts import KeyboardShortcutsComponent

# Pro import z adresáře mimo modernized použijte absolutní import
current_dir = os.path.abspath(os.path.dirname(__file__))
parent_dir = os.path.dirname(os.path.dirname(current_dir))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
from plugins.plugin_manager import PluginManager

# Predefined plugin order
PREDEFINED_ORDER = [
    "UzemniCelkyInspirePlugin",
    "BBoxPlugin",
    "MapPlugin",
    "OrtofotoDownloadPlugin",
    "VRTCreationPlugin",
    "ReprojectionPlugin",
    "KonecnyOrezUzemiPlugin",
    "LoggingPlugin"
]

class ModernMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Orto Pokrokové - Profesionální Zpracování")
        self.setObjectName("ModernMainWindow")  # Přidáno: nastavení objectName
        self.resize(1400, 900)
        
        # Inicializace komponent
        self._init_components()
        self._setup_layout()
        self._connect_signals()
        self._load_plugins()
        
        # Načtení uloženého stavu a geometrie okna
        self._restore_window_state()
        
        # Aplikace výchozího tématu
        self.theme_manager.apply_theme(
            light=self.settings_component.get_setting("general/theme", "light") == "light"
        )
        
        # Zobrazení uvítací zprávy
        QTimer.singleShot(500, self._show_welcome_message)

    def _init_components(self):
        """Inicializace všech komponent aplikace"""
        # Správce témat
        self.theme_manager = ThemeManager(self)
        
        # Komponenta nastavení
        self.settings_component = SettingsComponent(self)
        
        # Nástrojová lišta
        self.toolbar_component = ToolbarComponent(self)
        self.addToolBar(self.toolbar_component.toolbar)
        
        # Panel pluginů (levá strana)
        self.plugin_panel = PluginPanelComponent(self)
        self.plugin_panel.setObjectName("pluginPanel")  # Přidáno: nastavení objectName
        
        # Panel obsahu (pravá strana)
        self.content_panel = ContentPanelComponent(self)
        self.content_panel.setObjectName("contentPanel")  # Přidáno: nastavení objectName
        
        # Stavový panel
        self.status_panel = StatusPanelComponent(self)
        self.status_panel.set_version("1.0.0")
        
        # Systém notifikací
        self.notification = NotificationComponent(self)
        
        # Komponenta nápovědy
        self.help_component = HelpComponent(self)
        
        # Klávesové zkratky
        self.shortcuts_component = KeyboardShortcutsComponent(self)

    def _setup_layout(self):
        """Nastavení layoutu aplikace"""
        # Vytvoření splitteru pro levý a pravý panel
        self.splitter = QSplitter(Qt.Horizontal, self)
        self.splitter.setObjectName("mainSplitter")  # Přidáno: nastavení objectName
        self.splitter.addWidget(self.plugin_panel)
        self.splitter.addWidget(self.content_panel)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 4)
        self.splitter.setSizes([300, 1000])
        
        # Nastavení centrálního widgetu
        central_layout = QVBoxLayout()
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.addWidget(self.splitter)
        central_widget = QWidget(self)
        central_widget.setObjectName("centralWidget")  # Přidáno: nastavení objectName
        central_widget.setLayout(central_layout)
        self.setCentralWidget(central_widget)
        
    def _restore_window_state(self):
        """Obnoví uložený stav a geometrii okna"""
        # Obnovení geometrie okna
        geometry = self.settings_component.get_setting("window/geometry")
        if geometry:
            self.restoreGeometry(geometry)
            
        # Obnovení stavu okna (toolbary, docky, atd.)
        state = self.settings_component.get_setting("window/state")
        if state:
            self.restoreState(state)

    def _connect_signals(self):
        """Propojení signálů mezi komponentami"""
        # Propojení přepínání témat
        self.toolbar_component.theme_toggle_requested.connect(self.theme_manager.toggle_theme)
        self.theme_manager.is_light_theme_changed = lambda is_light: self.toolbar_component.update_theme_action_text(is_light)
        
        # Propojení výběru pluginu
        self.plugin_panel.plugin_selected.connect(self._on_plugin_selected)
        
        # Propojení nápovědy
        self.toolbar_component.action_help.triggered.connect(lambda: self.help_component.show_help())
        
        # Propojení klávesových zkratek
        self.shortcuts_component.shortcut_triggered.connect(self._handle_shortcut)
        
        # Propojení notifikací se stavovým panelem
        self.status_panel.notification_shown.connect(self._handle_notification)
        
        # Propojení nastavení
        self.settings_component.settings_changed.connect(self._handle_settings_changed)

    def _load_plugins(self):
        """Načtení pluginů"""
        # Získání nadřazeného adresáře pro načtení pluginů
        current_dir = os.path.abspath(os.path.dirname(__file__))
        parent_dir = os.path.dirname(os.path.dirname(current_dir))
        plugin_dir = os.path.join(parent_dir, "plugins")
        
        # Zobrazení indikátoru průběhu
        self.status_panel.show_progress(None)
        self.status_panel.show_message("Načítání pluginů...")
        
        # Inicializace správce pluginů
        self.plugin_manager = PluginManager(plugin_dir)
        plugins = self.plugin_manager.load_plugins(predefined_order=PREDEFINED_ORDER)
        
        # Přidání pluginů do komponent UI
        self.plugin_panel.add_plugins(plugins)
        self.content_panel.setup_plugin_stack(plugins)
        
        # Skrytí indikátoru průběhu
        self.status_panel.hide_progress()
        self.status_panel.show_message(f"Načteno {len(plugins)} pluginů", 3000)

    def _on_plugin_selected(self, index, plugin):
        """Obsluha výběru pluginu"""
        self.content_panel.switch_to_plugin(index)
        self.status_panel.show_message(f"Plugin aktivní: {plugin.name()}")
        
    def _handle_shortcut(self, action):
        """Obsluha klávesových zkratek"""
        if action == "help":
            self.help_component.show_help()
        elif action == "settings":
            self.settings_component.show_settings_dialog()
        elif action == "quit":
            self.close()
        elif action == "toggle_theme":
            self.theme_manager.toggle_theme()
        elif action == "next_plugin":
            current_index = self.plugin_panel.plugin_list.currentRow()
            next_index = (current_index + 1) % self.plugin_panel.plugin_list.count()
            self.plugin_panel.plugin_list.setCurrentRow(next_index)
        elif action == "prev_plugin":
            current_index = self.plugin_panel.plugin_list.currentRow()
            prev_index = (current_index - 1) % self.plugin_panel.plugin_list.count()
            self.plugin_panel.plugin_list.setCurrentRow(prev_index)
        elif action == "zoom_in":
            self.content_panel.preview_view.scale(1.25, 1.25)
        elif action == "zoom_out":
            self.content_panel.preview_view.scale(0.8, 0.8)
        elif action == "zoom_reset":
            self.content_panel.preview_view.reset_zoom()
            
    def _handle_notification(self, message, notification_type):
        """Obsluha notifikací ze stavového panelu"""
        if notification_type == 0:  # Info
            self.notification.show_notification(message, self.notification.INFO)
        elif notification_type == 1:  # Varování
            self.notification.show_notification(message, self.notification.WARNING)
        elif notification_type == 2:  # Chyba
            self.notification.show_notification(message, self.notification.ERROR)
            
    def _handle_settings_changed(self, changed_settings):
        """Obsluha změn nastavení"""
        # Aplikace změn tématu
        if "general/theme" in changed_settings:
            theme = changed_settings["general/theme"]
            if theme == "light":
                self.theme_manager.apply_theme(light=True)
            elif theme == "dark":
                self.theme_manager.apply_theme(light=False)
            elif theme == "system":
                # Zde by byla logika pro detekci systémového tématu
                pass
                
        # Zobrazení notifikace o změně nastavení
        self.status_panel.show_message("Nastavení bylo aktualizováno", 3000)
        
    def _show_welcome_message(self):
        """Zobrazí uvítací zprávu při spuštění aplikace"""
        self.notification.show_notification(
            "Vítejte v aplikaci Orto Pokrokové! Vyberte plugin v levém panelu pro začátek práce.",
            self.notification.INFO,
            8000
        )
        
    def closeEvent(self, event):
        """Obsluha události zavření okna"""
        # Kontrola, zda je potřeba uložit změny
        if self.settings_component.get_setting("general/confirm_exit", True, value_type=bool):
            reply = QMessageBox.question(
                self, 
                "Ukončit aplikaci", 
                "Opravdu chcete ukončit aplikaci?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.No:
                event.ignore()
                return
                
        # Uložení nastavení před ukončením
        self.settings_component.set_setting("window/geometry", self.saveGeometry())
        self.settings_component.set_setting("window/state", self.saveState())
        
        event.accept()
