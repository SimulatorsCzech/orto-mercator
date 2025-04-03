"""
Modul pro integraci logovacího systému s aplikací.
Zachytává standardní Python logy a výjimky.
"""

import sys
import logging
import traceback
from typing import Dict, Any, Optional, Callable

from PySide6.QtCore import QObject, Signal, Slot

from plugins.logging.log_manager import LogManager

class LoggingIntegration(QObject):
    """
    Třída pro integraci logovacího systému s aplikací.
    Zachytává standardní Python logy a výjimky.
    """
    
    # Signál pro oznámení, že byla zachycena výjimka
    exception_caught = Signal(str, str)
    
    def __init__(self, log_manager: LogManager):
        """
        Inicializace integrace.
        
        Args:
            log_manager: Správce logů
        """
        super().__init__()
        
        self.log_manager = log_manager
        
        # Nastavíme zachytávání výjimek
        self._setup_exception_handling()
        
        # Nastavíme zachytávání standardních Python logů
        self._setup_python_logging()
    
    def _setup_exception_handling(self):
        """
        Nastaví zachytávání výjimek.
        """
        # Uložíme původní handler výjimek
        self.original_excepthook = sys.excepthook
        
        # Nastavíme nový handler výjimek
        sys.excepthook = self._exception_handler
    
    def _setup_python_logging(self):
        """
        Nastaví zachytávání standardních Python logů.
        """
        # Vytvoříme handler pro zachytávání logů
        handler = LoggingIntegrationHandler(self.log_manager)
        
        # Nastavíme formát
        formatter = logging.Formatter('%(message)s')
        handler.setFormatter(formatter)
        
        # Přidáme handler do root loggeru
        root_logger = logging.getLogger()
        root_logger.addHandler(handler)
        
        # Nastavíme úroveň logování
        root_logger.setLevel(logging.DEBUG)
    
    def _exception_handler(self, exc_type, exc_value, exc_traceback):
        """
        Handler výjimek.
        
        Args:
            exc_type: Typ výjimky
            exc_value: Hodnota výjimky
            exc_traceback: Traceback výjimky
        """
        # Získáme traceback jako text
        tb_text = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        
        # Logujeme výjimku
        self.log_manager.add_log("CRITICAL", "Exception", f"Neošetřená výjimka: {exc_value}\n{tb_text}", use_python_logger=False)
        
        # Emitujeme signál
        self.exception_caught.emit(str(exc_value), tb_text)
        
        # Voláme původní handler
        self.original_excepthook(exc_type, exc_value, exc_traceback)
    
    def install_qt_message_handler(self):
        """
        Nainstaluje handler pro Qt zprávy.
        """
        from PySide6.QtCore import qInstallMessageHandler
        
        # Uložíme původní handler
        self.original_qt_message_handler = qInstallMessageHandler(None)
        
        # Nastavíme nový handler
        qInstallMessageHandler(self._qt_message_handler)
    
    def _qt_message_handler(self, msg_type, context, message):
        """
        Handler Qt zpráv.
        
        Args:
            msg_type: Typ zprávy
            context: Kontext zprávy
            message: Text zprávy
        """
        # Mapování typů zpráv na úrovně logů
        msg_type_map = {
            0: "DEBUG",     # QtDebugMsg
            1: "WARNING",   # QtWarningMsg
            2: "CRITICAL",  # QtCriticalMsg
            3: "CRITICAL",  # QtFatalMsg
            4: "INFO"       # QtInfoMsg
        }
        
        # Získáme úroveň logu
        level = msg_type_map.get(msg_type, "INFO")
        
        # Logujeme zprávu
        self.log_manager.add_log(level, "Qt", message, use_python_logger=False)
        
        # Voláme původní handler, pokud existuje
        if self.original_qt_message_handler:
            self.original_qt_message_handler(msg_type, context, message)
    
    def uninstall(self):
        """
        Odinstaluje integraci.
        """
        # Obnovíme původní handler výjimek
        sys.excepthook = self.original_excepthook
        
        # Odstraníme handler z root loggeru
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            if isinstance(handler, LoggingIntegrationHandler):
                root_logger.removeHandler(handler)
        
        # Obnovíme původní Qt handler, pokud byl nainstalován
        if hasattr(self, 'original_qt_message_handler'):
            from PySide6.QtCore import qInstallMessageHandler
            qInstallMessageHandler(self.original_qt_message_handler)

class LoggingIntegrationHandler(logging.Handler):
    """
    Handler pro zachytávání standardních Python logů.
    """
    
    def __init__(self, log_manager: LogManager):
        """
        Inicializace handleru.
        
        Args:
            log_manager: Správce logů
        """
        super().__init__()
        
        self.log_manager = log_manager
    
    def emit(self, record: logging.LogRecord):
        """
        Metoda volaná při emitování logu.
        
        Args:
            record: Záznam logu
        """
        try:
            # Mapování úrovní logů
            level_map = {
                logging.DEBUG: "DEBUG",
                logging.INFO: "INFO",
                logging.WARNING: "WARNING",
                logging.ERROR: "ERROR",
                logging.CRITICAL: "CRITICAL"
            }
            
            # Získáme úroveň logu
            level = level_map.get(record.levelno, "INFO")
            
            # Získáme zdroj logu
            source = record.name
            
            # Získáme zprávu
            message = self.format(record)
            
            # Přidáme log, ale nepoužijeme standardní Python logger
            # aby nedošlo k rekurzi
            self.log_manager.add_log(level, source, message, use_python_logger=False)
        except Exception:
            self.handleError(record)

def setup_global_exception_handling(log_manager: LogManager, show_dialog: bool = True):
    """
    Nastaví globální zachytávání výjimek.
    
    Args:
        log_manager: Správce logů
        show_dialog: Zda se má zobrazit dialog s výjimkou
    """
    # Vytvoříme integraci
    integration = LoggingIntegration(log_manager)
    
    # Pokud máme zobrazit dialog, připojíme signál
    if show_dialog:
        integration.exception_caught.connect(_show_exception_dialog)
    
    # Nainstalujeme Qt handler
    integration.install_qt_message_handler()
    
    return integration

def _show_exception_dialog(error_message: str, traceback_text: str):
    """
    Zobrazí dialog s výjimkou.
    
    Args:
        error_message: Chybová zpráva
        traceback_text: Text traceback
    """
    from PySide6.QtWidgets import QMessageBox
    
    # Vytvoříme dialog
    msg_box = QMessageBox()
    msg_box.setIcon(QMessageBox.Critical)
    msg_box.setWindowTitle("Neošetřená výjimka")
    msg_box.setText(f"V aplikaci došlo k neošetřené výjimce:\n{error_message}")
    msg_box.setDetailedText(traceback_text)
    msg_box.setStandardButtons(QMessageBox.Ok)
    
    # Zobrazíme dialog
    msg_box.exec_()