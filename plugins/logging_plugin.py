"""
Hlavní modul pro plugin logování.
Integruje všechny komponenty logovacího systému a poskytuje rozhraní pro aplikaci.
"""

import os
from typing import Dict, Any, Optional

from PySide6.QtWidgets import QWidget, QApplication
from PySide6.QtCore import QObject

from plugins.plugin_base import PluginBase
from plugins.logging.log_entry import LogEntry
from plugins.logging.log_manager import LogManager
from plugins.logging.log_enhanced_ui import LogEnhancedUI
from plugins.logging.log_integration import setup_global_exception_handling
from plugins.logging.log_config import LogConfig
from plugins.logging.log_rotation import LogRotationHandler, TimeBasedLogRotationHandler, cleanup_old_logs

class LoggingPlugin(PluginBase):
    """
    Plugin pro logování událostí v aplikaci.
    Poskytuje rozhraní pro zobrazení a správu logů.
    """
    
    def __init__(self, app_config: Dict[str, Any] = None):
        """
        Inicializace pluginu.
        
        Args:
            app_config: Konfigurace aplikace (výchozí: None)
        """
        super().__init__()
        
        # Pokud app_config není zadáno, vytvoříme prázdný slovník
        if app_config is None:
            app_config = {}
        
        # Vytvoříme konfiguraci pro logger
        self.log_config = LogConfig(app_config)
        
        # Vytvoříme správce logů
        self.log_manager = LogManager(self.log_config.get_all())
        
        # Nastavíme rotaci logů
        self._setup_log_rotation()
        
        # Nastavíme globální zachytávání výjimek
        self.integration = setup_global_exception_handling(self.log_manager)
        
        # Vyčistíme staré logy
        self._cleanup_old_logs()
        
        # Vytvoříme UI
        self.ui = None
        
        # Přidáme úvodní log
        self.log_manager.add_log("INFO", "LoggingPlugin", "Plugin pro logování byl inicializován")
    
    def _setup_log_rotation(self):
        """
        Nastaví rotaci log souborů.
        """
        # Zjistíme, zda je povolena rotace logů
        if self.log_config.get("log_rotation", True):
            # Zjistíme typ rotace
            rotation_type = self.log_config.get("rotation_type", "size")
            
            if rotation_type == "size":
                # Rotace podle velikosti
                handler = LogRotationHandler(
                    filename=self.log_config.get("log_file"),
                    max_bytes=self.log_config.get("max_log_file_size", 10 * 1024 * 1024),
                    backup_count=self.log_config.get("max_log_files", 5)
                )
            else:
                # Rotace podle času
                handler = TimeBasedLogRotationHandler(
                    filename=self.log_config.get("log_file"),
                    interval=self.log_config.get("rotation_interval", "daily"),
                    backup_count=self.log_config.get("max_log_files", 5)
                )
            
            # Nastavíme formát
            handler.setFormatter(self.log_manager.file_handler.formatter)
            
            # Nastavíme úroveň
            handler.setLevel(self.log_manager.file_handler.level)
            
            # Odstraníme původní handler
            self.log_manager.logger.removeHandler(self.log_manager.file_handler)
            
            # Přidáme nový handler
            self.log_manager.logger.addHandler(handler)
            
            # Uložíme handler
            self.log_manager.file_handler = handler
    
    def _cleanup_old_logs(self):
        """
        Vyčistí staré log soubory.
        """
        # Zjistíme, zda je povoleno čištění starých logů
        if self.log_config.get("cleanup_old_logs", True):
            # Zjistíme adresář s logy
            log_dir = os.path.dirname(self.log_config.get("log_file"))
            
            # Vyčistíme staré logy
            removed_count = cleanup_old_logs(
                log_dir=log_dir,
                max_age_days=self.log_config.get("max_log_age_days", 30)
            )
            
            # Přidáme log o vyčištění
            if removed_count > 0:
                self.log_manager.add_log("INFO", "LoggingPlugin", f"Bylo odstraněno {removed_count} starých log souborů")
    
    def name(self) -> str:
        """
        Vrátí název pluginu.
        
        Returns:
            Název pluginu
        """
        return "Logování"
    
    def description(self) -> str:
        """
        Vrátí popis pluginu.
        
        Returns:
            Popis pluginu
        """
        return "Plugin pro podrobné logování celého programu. Zaznamenává a zobrazuje podrobné logy o všech operacích v aplikaci."
    
    def get_default_config(self) -> dict:
        """
        Vrátí výchozí konfiguraci pluginu.
        
        Returns:
            Výchozí konfigurace
        """
        return self.log_config.DEFAULT_CONFIG
    
    def update_config(self, new_config: dict):
        """
        Aktualizuje konfiguraci pluginu.
        
        Args:
            new_config: Nová konfigurace
        """
        for key, value in new_config.items():
            self.log_config.set(key, value)
        self.log_config.save_config()
    
    def setup_ui(self, parent) -> QWidget:
        """
        Vrátí uživatelské rozhraní pluginu.
        
        Args:
            parent: Rodičovský widget
            
        Returns:
            Uživatelské rozhraní
        """
        if not self.ui:
            self.ui = LogEnhancedUI(self.log_manager, self.log_config, parent)
        
        return self.ui
    
    def execute(self, data):
        """
        Spouští logiku pluginu.
        
        Args:
            data: Data pro zpracování
        """
        # Tento plugin nemá žádnou speciální logiku pro spuštění
        pass
    
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
        
        # Odinstalujeme integraci
        if hasattr(self, 'integration'):
            self.integration.uninstall()
        
        # Ukončíme logger
        if hasattr(self, 'log_manager'):
            del self.log_manager