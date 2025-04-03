"""
Hlavní modul pro plugin logování.
Integruje všechny komponenty logovacího systému a poskytuje rozhraní pro aplikaci.
"""

import os
from typing import Dict, Any

from PySide6.QtWidgets import QWidget
from PySide6.QtCore import QObject

from plugins.plugin_base import PluginBase
from plugins.logging.log_entry import LogEntry
from plugins.logging.log_manager import LogManager
from plugins.logging.log_ui import LogViewWidget
from plugins.logging.log_signal_handler import LogSignalHandler

class LoggingPlugin(PluginBase):
    """
    Plugin pro logování událostí v aplikaci.
    Poskytuje rozhraní pro zobrazení a správu logů.
    """
    
    def __init__(self, app_config: Dict[str, Any] = None):
        """
        Inicializace pluginu.
        
        Args:
            app_config: Konfigurace aplikace
        """
        super().__init__()
        
        # Vytvoříme konfiguraci pro logger
        app_data_dir = ""
        if app_config is not None and isinstance(app_config, dict):
            app_data_dir = app_config.get("app_data_dir", "")
            
        self.config = {
            "log_file": os.path.join(app_data_dir, "logs", "ortofoto_app.log"),
            "max_log_entries": 1000,
            "log_level": "INFO",
            "auto_scroll": True,
            "log_to_file": True
        }
        
        # Vytvoříme správce logů
        self.log_manager = LogManager(self.config)
        
        # Vytvoříme handler signálů
        self.signal_handler = LogSignalHandler(self.log_manager)
        
        # Vytvoříme UI (LogViewWidget místo LoggingUI)
        self.ui = None
        
        # Přidáme úvodní log
        self.log_manager.add_log("INFO", "LoggingPlugin", "Plugin pro logování byl inicializován")
    
    def get_name(self) -> str:
        """
        Vrátí název pluginu.
        
        Returns:
            Název pluginu
        """
        return "Logování"
    
    def get_description(self) -> str:
        """
        Vrátí popis pluginu.
        
        Returns:
            Popis pluginu
        """
        return "Plugin pro podrobné logování celého programu. Zaznamenává a zobrazuje podrobné logy o všech operacích v aplikaci."
    
    def get_icon(self) -> str:
        """
        Vrátí cestu k ikoně pluginu.
        
        Returns:
            Cesta k ikoně
        """
        return "icons/log.png"
    
    def get_ui(self) -> QWidget:
        """
        Vrátí uživatelské rozhraní pluginu.
        
        Returns:
            Uživatelské rozhraní
        """
        if not self.ui:
            self.ui = LogViewWidget(self.log_manager)
        
        return self.ui
    
    def log(self, level: str, message: str) -> LogEntry:
        """
        Přidá nový záznam do logu.
        
        Args:
            level: Úroveň logu (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            message: Zpráva logu
            
        Returns:
            Vytvořený záznam logu
        """
        return self.log_manager.add_log(level, "LoggingPlugin", message)
    
    def debug(self, message: str) -> LogEntry:
        """
        Přidá nový DEBUG záznam do logu.
        
        Args:
            message: Zpráva logu
            
        Returns:
            Vytvořený záznam logu
        """
        return self.log_manager.add_log("DEBUG", "LoggingPlugin", message)
    
    def info(self, message: str) -> LogEntry:
        """
        Přidá nový INFO záznam do logu.
        
        Args:
            message: Zpráva logu
            
        Returns:
            Vytvořený záznam logu
        """
        return self.log_manager.add_log("INFO", "LoggingPlugin", message)
    
    def warning(self, message: str) -> LogEntry:
        """
        Přidá nový WARNING záznam do logu.
        
        Args:
            message: Zpráva logu
            
        Returns:
            Vytvořený záznam logu
        """
        return self.log_manager.add_log("WARNING", "LoggingPlugin", message)
    
    def error(self, message: str) -> LogEntry:
        """
        Přidá nový ERROR záznam do logu.
        
        Args:
            message: Zpráva logu
            
        Returns:
            Vytvořený záznam logu
        """
        return self.log_manager.add_log("ERROR", "LoggingPlugin", message)
    
    def critical(self, message: str) -> LogEntry:
        """
        Přidá nový CRITICAL záznam do logu.
        
        Args:
            message: Zpráva logu
            
        Returns:
            Vytvořený záznam logu
        """
        return self.log_manager.add_log("CRITICAL", "LoggingPlugin", message)
    
    def on_plugin_loaded(self):
        """
        Metoda volaná při načtení pluginu.
        """
        self.info("Plugin pro logování byl načten")
    
    def on_plugin_unloaded(self):
        """
        Metoda volaná při uvolnění pluginu.
        """
        self.info("Plugin pro logování byl uvolněn")
        
        # Ukončíme logger
        if hasattr(self, 'log_manager'):
            del self.log_manager
