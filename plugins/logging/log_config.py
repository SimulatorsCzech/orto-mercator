"""
Modul obsahující třídu pro konfiguraci logovacího systému.
"""

import os
import json
from typing import Dict, Any, Optional

class LogConfig:
    """
    Třída pro konfiguraci logovacího systému.
    Umožňuje načítání a ukládání nastavení.
    """
    
    # Výchozí hodnoty konfigurace
    DEFAULT_CONFIG = {
        "log_file": "logs/ortofoto_app.log",
        "max_log_entries": 1000,
        "log_level": "INFO",
        "auto_scroll": True,
        "log_to_file": True,
        "log_rotation": True,
        "max_log_file_size": 10 * 1024 * 1024,  # 10 MB
        "max_log_files": 5,
        "show_debug_logs": False,
        "ui_theme": "light",
        "export_formats": ["log", "txt", "csv", "html", "json"],
        "default_export_format": "log"
    }
    
    def __init__(self, app_config: Dict[str, Any]):
        """
        Inicializace konfigurace.
        
        Args:
            app_config: Konfigurace aplikace
        """
        self.app_config = app_config or {}
        self.config = self.DEFAULT_CONFIG.copy()
        
        # Cesta ke konfiguračnímu souboru
        self.config_file = os.path.join(
            app_config.get("app_data_dir", ""),
            "config",
            "logging_config.json"
        )
        
        # Načteme konfiguraci
        self.load_config()
        
        # Aktualizujeme cesty
        self._update_paths()
    
    def _update_paths(self):
        """
        Aktualizuje cesty v konfiguraci podle adresáře aplikace.
        """
        # Aktualizujeme cestu k log souboru
        if not os.path.isabs(self.config["log_file"]):
            self.config["log_file"] = os.path.join(
                self.app_config.get("app_data_dir", ""),
                self.config["log_file"]
            )
        
        # Vytvoříme adresář pro logy, pokud neexistuje
        log_dir = os.path.dirname(self.config["log_file"])
        os.makedirs(log_dir, exist_ok=True)
    
    def load_config(self) -> bool:
        """
        Načte konfiguraci ze souboru.
        
        Returns:
            True pokud se načtení podařilo, jinak False
        """
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                
                # Aktualizujeme konfiguraci
                self.config.update(loaded_config)
                return True
            else:
                # Vytvoříme adresář pro konfiguraci, pokud neexistuje
                os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
                
                # Uložíme výchozí konfiguraci
                self.save_config()
                return False
        except Exception as e:
            print(f"Chyba při načítání konfigurace: {str(e)}")
            return False
    
    def save_config(self) -> bool:
        """
        Uloží konfiguraci do souboru.
        
        Returns:
            True pokud se uložení podařilo, jinak False
        """
        try:
            # Vytvoříme adresář pro konfiguraci, pokud neexistuje
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            
            # Uložíme konfiguraci
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
            
            return True
        except Exception as e:
            print(f"Chyba při ukládání konfigurace: {str(e)}")
            return False
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Vrátí hodnotu konfigurace pro daný klíč.
        
        Args:
            key: Klíč konfigurace
            default: Výchozí hodnota, pokud klí�� neexistuje
            
        Returns:
            Hodnota konfigurace
        """
        return self.config.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """
        Nastaví hodnotu konfigurace pro daný klíč.
        
        Args:
            key: Klíč konfigurace
            value: Hodnota konfigurace
        """
        self.config[key] = value
    
    def get_all(self) -> Dict[str, Any]:
        """
        Vrátí celou konfiguraci.
        
        Returns:
            Konfigurace
        """
        return self.config.copy()
    
    def reset(self) -> None:
        """
        Resetuje konfiguraci na výchozí hodnoty.
        """
        self.config = self.DEFAULT_CONFIG.copy()
        self._update_paths()
        self.save_config()