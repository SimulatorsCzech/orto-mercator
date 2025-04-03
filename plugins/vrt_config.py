"""
Konfigurace pro tvorbu VRT vrstvy.
"""

import os
from dataclasses import dataclass, field
from typing import Optional, Dict, Any

@dataclass
class VRTCreationConfig:
    """Konfigurace pro tvorbu VRT vrstvy"""
    
    # Základní nastavení
    max_workers: int = field(default_factory=lambda: os.cpu_count() or 4)
    batch_size: int = 100
    max_tile_conversion_attempts: int = 3
    tile_conversion_timeout: int = 600  # sekund
    
    # Nastavení zpracování
    downscale: Optional[float] = None
    downscale_resampling: str = "lanczos"
    resampling: str = "nearest"
    resolution: str = "highest"  # "highest" nebo "lowest"
    nodata: Optional[int] = None
    
    # Nastavení výstupu
    create_jpg: bool = True
    delete_png: bool = False
    delete_mercator: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Převede konfiguraci na slovník"""
        return {
            "max_workers": self.max_workers,
            "batch_size": self.batch_size,
            "max_tile_conversion_attempts": self.max_tile_conversion_attempts,
            "tile_conversion_timeout": self.tile_conversion_timeout,
            "downscale": self.downscale,
            "downscale_resampling": self.downscale_resampling,
            "resampling": self.resampling,
            "resolution": self.resolution,
            "nodata": self.nodata,
            "create_jpg": self.create_jpg,
            "delete_png": self.delete_png,
            "delete_mercator": self.delete_mercator
        }
    
    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'VRTCreationConfig':
        """Vytvoří konfiguraci ze slovníku"""
        # Vytvoříme instanci s výchozími hodnotami
        config = cls()
        
        # Aktualizujeme hodnoty ze slovníku
        for key, value in config_dict.items():
            if hasattr(config, key):
                setattr(config, key, value)
        
        return config
    
    def validate(self) -> Dict[str, str]:
        """Validuje konfiguraci a vrací slovník chyb"""
        errors = {}
        
        # Validace max_workers
        if self.max_workers <= 0:
            errors["max_workers"] = "Počet vláken musí být větší než 0"
        
        # Validace batch_size
        if self.batch_size <= 0:
            errors["batch_size"] = "Velikost dávky musí být větší než 0"
        
        # Validace max_tile_conversion_attempts
        if self.max_tile_conversion_attempts <= 0:
            errors["max_tile_conversion_attempts"] = "Počet pokusů musí být větší než 0"
        
        # Validace tile_conversion_timeout
        if self.tile_conversion_timeout <= 0:
            errors["tile_conversion_timeout"] = "Timeout musí být větší než 0"
        
        # Validace downscale
        if self.downscale is not None and self.downscale <= 0:
            errors["downscale"] = "Hodnota downscale musí být větší než 0"
        
        # Validace resampling metod
        valid_resampling = ["nearest", "near", "bilinear", "cubic", "cubicspline", "lanczos", "average", "mode"]
        if self.resampling not in valid_resampling:
            errors["resampling"] = f"Neplatná metoda resamplingu. Povolené hodnoty: {', '.join(valid_resampling)}"
        
        if self.downscale_resampling not in valid_resampling:
            errors["downscale_resampling"] = f"Neplatná metoda resamplingu. Povolené hodnoty: {', '.join(valid_resampling)}"
        
        # Validace resolution
        if self.resolution not in ["highest", "lowest", "average"]:
            errors["resolution"] = "Neplatná hodnota resolution. Povolené hodnoty: highest, lowest, average"
        
        return errors