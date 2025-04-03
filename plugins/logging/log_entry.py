"""
Modul obsahující třídu LogEntry pro reprezentaci jednoho záznamu v logu.
"""

from datetime import datetime
from PySide6.QtGui import QColor

class LogEntry:
    """
    Třída reprezentující jeden záznam v logu.
    """
    
    def __init__(self, level: str, source: str, message: str, timestamp: datetime = None):
        """
        Inicializace záznamu v logu.
        
        Args:
            level: Úroveň logu (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            source: Zdroj logu (název pluginu nebo komponenty)
            message: Zpráva logu
            timestamp: Časová značka (výchozí je aktuální čas)
        """
        self.level = level
        self.source = source
        self.message = message
        self.timestamp = timestamp or datetime.now()
    
    def __str__(self) -> str:
        """
        Vrátí textovou reprezentaci záznamu v logu.
        
        Returns:
            Textová reprezentace záznamu
        """
        return f"[{self.timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}] [{self.level}] [{self.source}] {self.message}"
    
    def get_color(self) -> QColor:
        """
        Vrátí barvu pro danou úroveň logu.
        
        Returns:
            Barva pro danou úroveň logu
        """
        if self.level == "DEBUG":
            return QColor(100, 100, 100)  # Šedá
        elif self.level == "INFO":
            return QColor(0, 0, 0)        # Černá
        elif self.level == "WARNING":
            return QColor(255, 165, 0)    # Oranžová
        elif self.level == "ERROR":
            return QColor(255, 0, 0)      # Červená
        elif self.level == "CRITICAL":
            return QColor(139, 0, 0)      # Tmavě červená
        else:
            return QColor(0, 0, 0)        # Černá