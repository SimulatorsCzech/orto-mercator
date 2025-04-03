"""
Modul obsahující třídu LogManager pro správu logů.
"""

import os
import logging
from typing import List, Set, Optional
from datetime import datetime

from PySide6.QtCore import QObject, Signal

from plugins.logging.log_entry import LogEntry

# Formát logu: [čas] [úroveň] [zdroj] zpráva
log_formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s')

class LogManager(QObject):
    """
    Třída pro správu logů. Uchovává záznamy, filtruje je a poskytuje rozhraní pro práci s nimi.
    """
    
    # Signál pro oznámení, že byl přidán nový záznam
    log_added = Signal(LogEntry)
    
    # Signál pro oznámení, že se změnil seznam zdrojů
    sources_changed = Signal(set)
    
    def __init__(self, config: dict = None):
        """
        Inicializace správce logů.
        
        Args:
            config: Konfigurace loggeru
        """
        super().__init__()
        
        # Výchozí konfigurace
        default_config = {
            "log_file": "logs/ortofoto_app.log",
            "max_log_entries": 1000,
            "log_level": "INFO",
            "log_to_file": True
        }
        
        # Použijeme dodanou konfiguraci nebo výchozí
        self.config = default_config.copy()
        if config:
            self.config.update(config)
        
        self.log_entries: List[LogEntry] = []
        self.log_sources: Set[str] = set()
        
        # Příznak pro prevenci rekurze
        self._in_add_log = False
        
        # Vytvoříme adresář pro logy, pokud neexistuje
        log_dir = os.path.dirname(self.config["log_file"])
        if log_dir:  # Kontrola, zda log_dir není prázdný řetězec
            os.makedirs(log_dir, exist_ok=True)
        
        # Nastavíme standardní Python logger
        self.logger = logging.getLogger("OrtofotoApp")
        self.logger.setLevel(logging.DEBUG)
        
        # Nastavíme handler pro ukládání do souboru
        self.file_handler = logging.FileHandler(self.config["log_file"], encoding="utf-8")
        self.file_handler.setFormatter(log_formatter)
        self.file_handler.setLevel(logging.INFO)
        
        # Přidáme handler pouze pokud je povoleno ukládání do souboru
        if self.config["log_to_file"]:
            self.logger.addHandler(self.file_handler)
    
    def add_log(self, level: str, source: str, message: str, use_python_logger: bool = True) -> LogEntry:
        """
        Přidá nový záznam do logu.
        
        Args:
            level: Úroveň logu (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            source: Zdroj logu (název pluginu nebo komponenty)
            message: Zpráva logu
            use_python_logger: Zda se má použít standardní Python logger
            
        Returns:
            Vytvořený záznam logu
        """
        # Prevence rekurze
        if self._in_add_log:
            return None
        
        self._in_add_log = True
        
        try:
            # Vytvoříme nový záznam
            log_entry = LogEntry(level, source, message)
            
            # Přidáme zdroj do seznamu zdrojů
            if source not in self.log_sources:
                self.log_sources.add(source)
                self.sources_changed.emit(self.log_sources)
            
            # Přidáme záznam do seznamu
            self.log_entries.append(log_entry)
            
            # Omezíme počet záznamů
            if len(self.log_entries) > self.config["max_log_entries"]:
                self.log_entries = self.log_entries[-self.config["max_log_entries"]:]
            
            # Logujeme do standardního Python loggeru, pokud je to povoleno
            if use_python_logger:
                # Mapování úrovní
                level_map = {
                    "DEBUG": logging.DEBUG,
                    "INFO": logging.INFO,
                    "WARNING": logging.WARNING,
                    "ERROR": logging.ERROR,
                    "CRITICAL": logging.CRITICAL
                }
                
                # Získáme úroveň logu
                log_level = level_map.get(level, logging.INFO)
                
                # Logujeme zprávu
                self.logger.log(log_level, message)
            
            # Emitujeme signál o přidání nového záznamu
            self.log_added.emit(log_entry)
            
            return log_entry
        finally:
            self._in_add_log = False
    
    def get_filtered_logs(self, level: str = "ALL", source: str = "ALL") -> List[LogEntry]:
        """
        Vrátí filtrované záznamy podle úrovně a zdroje.
        
        Args:
            level: Úroveň logu pro filtrování ("ALL" pro všechny úrovně)
            source: Zdroj logu pro filtrování ("ALL" pro všechny zdroje)
            
        Returns:
            Seznam filtrovaných záznamů
        """
        filtered_logs = []
        
        for entry in self.log_entries:
            # Filtrujeme podle úrovně
            if level != "ALL" and entry.level != level:
                continue
            
            # Filtrujeme podle zdroje
            if source != "ALL" and entry.source != source:
                continue
            
            filtered_logs.append(entry)
        
        return filtered_logs
    
    def clear_logs(self):
        """
        Vyčistí všechny logy.
        """
        self.log_entries = []
        
        # Přidáme informaci o vyčištění
        self.add_log("INFO", "LoggingPlugin", "Logy byly vyčištěny")
    
    def save_logs_to_file(self, file_path: str) -> bool:
        """
        Uloží všechny logy do souboru.
        
        Args:
            file_path: Cesta k souboru pro uložení
            
        Returns:
            True pokud se uložení podařilo, jinak False
        """
        try:
            # Uložíme logy do souboru
            with open(file_path, "w", encoding="utf-8") as f:
                for entry in self.log_entries:
                    f.write(str(entry) + "\n")
            
            # Přidáme informaci o uložení
            self.add_log("INFO", "LoggingPlugin", f"Logy byly uloženy do souboru: {file_path}")
            
            return True
            
        except Exception as e:
            # Přidáme informaci o chybě
            self.add_log("ERROR", "LoggingPlugin", f"Chyba p��i ukládání logů do souboru {file_path}: {str(e)}")
            
            return False
    
    def set_log_to_file(self, enabled: bool):
        """
        Nastaví, zda se mají logy ukládat do souboru.
        
        Args:
            enabled: True pro povolení ukládání do souboru, jinak False
        """
        # Aktualizujeme konfiguraci
        self.config["log_to_file"] = enabled
        
        # Přidáme nebo odebereme handler pro ukládání do souboru
        if enabled:
            if self.file_handler not in self.logger.handlers:
                self.logger.addHandler(self.file_handler)
            self.add_log("INFO", "LoggingPlugin", f"Ukládání logů do souboru zapnuto: {self.config['log_file']}")
        else:
            if self.file_handler in self.logger.handlers:
                self.logger.removeHandler(self.file_handler)
            self.add_log("INFO", "LoggingPlugin", "Ukládání logů do souboru vypnuto")
    
    def __del__(self):
        """
        Destruktor - zajistí korektní ukončení loggeru.
        """
        # Odebereme handler pro ukládání do souboru
        if hasattr(self, 'file_handler') and hasattr(self, 'logger'):
            if self.file_handler in self.logger.handlers:
                self.logger.removeHandler(self.file_handler)
                self.file_handler.close()