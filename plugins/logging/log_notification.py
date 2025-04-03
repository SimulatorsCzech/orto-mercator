"""
Modul pro notifikace o důležitých událostech v logu.
"""

import os
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                              QPushButton, QSystemTrayIcon, QMenu, QApplication)
from PySide6.QtCore import Qt, QTimer, Signal, Slot, QObject
from PySide6.QtGui import QIcon, QPixmap, QColor

from plugins.logging.log_entry import LogEntry
from plugins.logging.log_manager import LogManager

class LogNotifier(QObject):
    """
    Třída pro notifikace o důležitých událostech v logu.
    """
    
    # Signál pro oznámení, že byla přidána nová důležitá událost
    important_event = Signal(LogEntry)
    
    def __init__(self, log_manager: LogManager, config: Dict[str, Any]):
        """
        Inicializace notifikátoru.
        
        Args:
            log_manager: Správce logů
            config: Konfigurace notifikací
        """
        super().__init__()
        
        self.log_manager = log_manager
        self.config = config
        
        # Nastavíme výchozí konfiguraci
        self.default_config = {
            "notify_error": True,
            "notify_critical": True,
            "notify_warning": False,
            "notification_timeout": 5000,  # 5 sekund
            "notification_sound": True,
            "notification_icon": "icons/log_notification.png",
            "notification_limit": 5,  # Maximální počet notifikací za minutu
            "notification_cooldown": 60  # Cooldown v sekundách
        }
        
        # Aktualizujeme konfiguraci
        for key, value in self.default_config.items():
            if key not in self.config:
                self.config[key] = value
        
        # Seznam posledních notifikací
        self.recent_notifications = []
        
        # Vytvoříme systémovou ikonu, pokud je podporována
        self.tray_icon = None
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.setup_tray_icon()
        
        # Připojíme signály
        self._connect_signals()
    
    def setup_tray_icon(self):
        """
        Nastaví systémovou ikonu.
        """
        # Vytvoříme ikonu
        self.tray_icon = QSystemTrayIcon()
        
        # Nastavíme ikonu
        icon_path = self.config.get("notification_icon", "icons/log_notification.png")
        if os.path.exists(icon_path):
            self.tray_icon.setIcon(QIcon(icon_path))
        else:
            # Použijeme výchozí ikonu
            self.tray_icon.setIcon(QApplication.style().standardIcon(QApplication.style().SP_MessageBoxInformation))
        
        # Vytvoříme menu
        menu = QMenu()
        
        # Přidáme akce
        show_action = menu.addAction("Zobrazit logy")
        show_action.triggered.connect(self._on_show_logs)
        
        menu.addSeparator()
        
        exit_action = menu.addAction("Ukončit")
        exit_action.triggered.connect(QApplication.quit)
        
        # Nastavíme menu
        self.tray_icon.setContextMenu(menu)
        
        # Zobrazíme ikonu
        self.tray_icon.show()
    
    def _connect_signals(self):
        """
        Připojí signály k příslušným slotům.
        """
        # Připojení signálu pro přidání nového logu
        self.log_manager.log_added.connect(self._on_log_added)
    
    def _on_log_added(self, log_entry: LogEntry):
        """
        Slot volaný při přidání nového logu.
        
        Args:
            log_entry: Nový záznam logu
        """
        # Kontrolujeme, zda je log důležitý
        if self._is_important_log(log_entry):
            # Kontrolujeme, zda nejsme v cooldownu
            if self._check_notification_limit():
                # Přidáme notifikaci do seznamu
                self.recent_notifications.append(datetime.now())
                
                # Emitujeme signál
                self.important_event.emit(log_entry)
                
                # Zobrazíme notifikaci
                self._show_notification(log_entry)
    
    def _is_important_log(self, log_entry: LogEntry) -> bool:
        """
        Zkontroluje, zda je log důležitý.
        
        Args:
            log_entry: Záznam logu
            
        Returns:
            True pokud je log důležitý, jinak False
        """
        if log_entry.level == "ERROR" and self.config.get("notify_error", True):
            return True
        elif log_entry.level == "CRITICAL" and self.config.get("notify_critical", True):
            return True
        elif log_entry.level == "WARNING" and self.config.get("notify_warning", False):
            return True
        
        return False
    
    def _check_notification_limit(self) -> bool:
        """
        Zkontroluje, zda nejsme v cooldownu.
        
        Returns:
            True pokud můžeme zobrazit notifikaci, jinak False
        """
        # Zjistíme aktuální čas
        now = datetime.now()
        
        # Odstraníme staré notifikace
        self.recent_notifications = [n for n in self.recent_notifications 
                                    if n > now - timedelta(seconds=self.config.get("notification_cooldown", 60))]
        
        # Zkontrolujeme, zda nepřekračujeme limit
        return len(self.recent_notifications) < self.config.get("notification_limit", 5)
    
    def _show_notification(self, log_entry: LogEntry):
        """
        Zobrazí notifikaci.
        
        Args:
            log_entry: Záznam logu
        """
        # Pokud nemáme systémovou ikonu, nemůžeme zobrazit notifikaci
        if not self.tray_icon:
            return
        
        # Vytvoříme titulek
        title = f"Log: {log_entry.level}"
        
        # Vytvoříme zprávu
        message = f"[{log_entry.source}] {log_entry.message}"
        
        # Nastavíme ikonu podle úrovně
        icon = QSystemTrayIcon.Information
        if log_entry.level == "WARNING":
            icon = QSystemTrayIcon.Warning
        elif log_entry.level == "ERROR" or log_entry.level == "CRITICAL":
            icon = QSystemTrayIcon.Critical
        
        # Zobrazíme notifikaci
        self.tray_icon.showMessage(
            title,
            message,
            icon,
            self.config.get("notification_timeout", 5000)
        )
    
    def _on_show_logs(self):
        """
        Slot volaný při kliknutí na 'Zobrazit logy'.
        """
        # Tuto metodu by měla implementovat aplikace
        pass

class NotificationWidget(QWidget):
    """
    Widget pro zobrazení notifikace.
    """
    
    # Signál pro oznámení, že byla notifikace zavřena
    closed = Signal()
    
    def __init__(self, log_entry: LogEntry, parent: QWidget = None):
        """
        Inicializace widgetu.
        
        Args:
            log_entry: Záznam logu
            parent: Rodičovský widget
        """
        super().__init__(parent)
        
        self.log_entry = log_entry
        
        # Nastavíme vlastnosti widgetu
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # Vytvoříme UI
        self._setup_ui()
        
        # Nastavíme časovač pro automatické zavření
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.close)
        self.timer.start(5000)  # 5 sekund
    
    def _setup_ui(self):
        """
        Vytvoří uživatelské rozhraní.
        """
        # Vytvoříme hlavní layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Vytvoříme widget pro notifikaci
        notification_widget = QWidget(self)
        notification_widget.setObjectName("notification_widget")
        notification_widget.setStyleSheet("""
            #notification_widget {
                background-color: #f0f0f0;
                border: 1px solid #cccccc;
                border-radius: 5px;
            }
        """)
        
        notification_layout = QVBoxLayout(notification_widget)
        
        # Vytvoříme horní panel
        header_layout = QHBoxLayout()
        
        # Ikona podle úrovně
        icon_label = QLabel(self)
        if self.log_entry.level == "WARNING":
            icon_label.setPixmap(QApplication.style().standardIcon(QApplication.style().SP_MessageBoxWarning).pixmap(16, 16))
        elif self.log_entry.level == "ERROR" or self.log_entry.level == "CRITICAL":
            icon_label.setPixmap(QApplication.style().standardIcon(QApplication.style().SP_MessageBoxCritical).pixmap(16, 16))
        else:
            icon_label.setPixmap(QApplication.style().standardIcon(QApplication.style().SP_MessageBoxInformation).pixmap(16, 16))
        
        header_layout.addWidget(icon_label)
        
        # Titulek
        title_label = QLabel(f"Log: {self.log_entry.level}", self)
        title_label.setStyleSheet("font-weight: bold;")
        header_layout.addWidget(title_label)
        
        # Tlačítko pro zavření
        close_button = QPushButton("×", self)
        close_button.setFixedSize(16, 16)
        close_button.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                color: #666666;
                font-weight: bold;
            }
            QPushButton:hover {
                color: #ff0000;
            }
        """)
        close_button.clicked.connect(self.close)
        header_layout.addWidget(close_button)
        
        notification_layout.addLayout(header_layout)
        
        # Zpráva
        message_label = QLabel(f"[{self.log_entry.source}] {self.log_entry.message}", self)
        message_label.setWordWrap(True)
        notification_layout.addWidget(message_label)
        
        # Čas
        time_label = QLabel(self.log_entry.timestamp.strftime("%H:%M:%S"), self)
        time_label.setStyleSheet("color: #666666;")
        time_label.setAlignment(Qt.AlignRight)
        notification_layout.addWidget(time_label)
        
        layout.addWidget(notification_widget)
    
    def closeEvent(self, event):
        """
        Metoda volaná při zavření widgetu.
        
        Args:
            event: Událost zavření
        """
        # Emitujeme signál
        self.closed.emit()
        
        # Pokračujeme v události
        super().closeEvent(event)

class NotificationManager(QObject):
    """
    Správce notifikací.
    """
    
    def __init__(self, log_manager: LogManager, config: Dict[str, Any]):
        """
        Inicializace správce.
        
        Args:
            log_manager: Správce logů
            config: Konfigurace notifikací
        """
        super().__init__()
        
        self.log_manager = log_manager
        self.config = config
        
        # Vytvoříme notifikátor
        self.notifier = LogNotifier(log_manager, config)
        
        # Seznam aktivních notifikací
        self.active_notifications = []
        
        # Připojíme signály
        self.notifier.important_event.connect(self._on_important_event)
    
    def _on_important_event(self, log_entry: LogEntry):
        """
        Slot volaný při důležité události.
        
        Args:
            log_entry: Záznam logu
        """
        # Vytvoříme widget pro notifikaci
        notification = NotificationWidget(log_entry)
        
        # Připojíme signál pro zavření
        notification.closed.connect(lambda: self._on_notification_closed(notification))
        
        # Přidáme notifikaci do seznamu
        self.active_notifications.append(notification)
        
        # Aktualizujeme pozice notifikací
        self._update_notification_positions()
        
        # Zobrazíme notifikaci
        notification.show()
    
    def _on_notification_closed(self, notification: NotificationWidget):
        """
        Slot volaný při zavření notifikace.
        
        Args:
            notification: Widget notifikace
        """
        # Odstraníme notifikaci ze seznamu
        if notification in self.active_notifications:
            self.active_notifications.remove(notification)
        
        # Aktualizujeme pozice notifikací
        self._update_notification_positions()
    
    def _update_notification_positions(self):
        """
        Aktualizuje pozice notifikací.
        """
        # Zjistíme velikost obrazovky
        screen = QApplication.primaryScreen().geometry()
        
        # Nastavíme pozice notifikací
        for i, notification in enumerate(self.active_notifications):
            # Zjistíme velikost notifikace
            notification_size = notification.sizeHint()
            
            # Vypočítáme pozici
            x = screen.width() - notification_size.width() - 20
            y = screen.height() - notification_size.height() * (i + 1) - 20 * (i + 1)
            
            # Nastavíme pozici
            notification.move(x, y)