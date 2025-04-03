from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QPoint, QSize
from PySide6.QtGui import QColor, QPainter, QPainterPath, QFont, QAction

class NotificationComponent(QWidget):
    """Komponenta pro zobrazování vyskakovacích notifikací"""
    
    INFO = 0
    WARNING = 1
    ERROR = 2
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self._init_ui()
        self.notifications = []
        # Uchovává aktivní animace, aby nedošlo k jejich garbage collection
        self.active_animations = []
        
    def _init_ui(self):
        # Nastavení vlastností widgetu
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        
        # Vytvoření layoutu
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Kontejner pro notifikace
        self.notification_container = QWidget(self)
        self.notification_layout = QVBoxLayout(self.notification_container)
        self.notification_layout.setContentsMargins(0, 0, 0, 0)
        self.notification_layout.setSpacing(10)
        layout.addWidget(self.notification_container)
        
    def show_notification(self, message, notification_type=INFO, timeout=5000):
        """Zobrazí novou notifikaci"""
        # Vytvoření notifikačního widgetu
        notification = self._create_notification_widget(message, notification_type)
        
        # Přidání do layoutu
        self.notification_layout.addWidget(notification)
        self.notifications.append(notification)
        
        # Nastavení pozice
        self._position_notifications()
        
        # Zobrazení
        self.show()
        
        # Animace zobrazení
        self._animate_notification_in(notification)
        
        # Automatické skrytí po timeoutu
        if timeout > 0:
            QTimer.singleShot(timeout, lambda: self._remove_notification(notification))
    
    def _create_notification_widget(self, message, notification_type):
        """Vytvoří widget pro notifikaci"""
        notification = QWidget(self.notification_container)
        notification.setObjectName("notification")
        
        # Nastavení stylu podle typu
        if notification_type == self.INFO:
            bg_color = "#2196F3"
            icon = "ℹ️"
        elif notification_type == self.WARNING:
            bg_color = "#FF9800"
            icon = "⚠️"
        else:  # ERROR
            bg_color = "#F44336"
            icon = "❌"
            
        notification.setStyleSheet(f"""
            QWidget#notification {{
                background-color: {bg_color};
                border-radius: 6px;
                color: white;
            }}
            QLabel {{
                color: white;
            }}
            QPushButton {{
                background-color: transparent;
                color: white;
                border: none;
                font-weight: bold;
                padding: 4px;
            }}
            QPushButton:hover {{
                background-color: rgba(255, 255, 255, 0.2);
                border-radius: 4px;
            }}
        """)
        
        # Vytvoření layoutu notifikace
        layout = QHBoxLayout(notification)
        layout.setContentsMargins(12, 12, 12, 12)
        
        # Ikona
        icon_label = QLabel(icon)
        icon_label.setFont(QFont("Segoe UI", 14))
        layout.addWidget(icon_label)
        
        # Zpráva
        message_label = QLabel(message)
        message_label.setWordWrap(True)
        layout.addWidget(message_label, 1)
        
        # Tlačítko zavřít
        close_button = QPushButton("×")
        close_button.setFont(QFont("Segoe UI", 14))
        close_button.clicked.connect(lambda: self._remove_notification(notification))
        layout.addWidget(close_button)
        
        # Nastavení fixní šířky a minimální výšky
        notification.setFixedWidth(300)
        notification.setMinimumHeight(50)
        
        return notification
    
    def _position_notifications(self):
        """Umístí notifikace na správnou pozici"""
        if not self.parent:
            return
            
        # Umístění v pravém horním rohu rodičovského widgetu
        parent_rect = self.parent.geometry()
        self.move(parent_rect.right() - self.width() - 20, parent_rect.top() + 40)
        
    def _animate_notification_in(self, notification):
        """Animuje zobrazení notifikace"""
        animation = QPropertyAnimation(notification, b"pos")
        animation.setDuration(300)
        
        # Počáteční pozice (mimo obrazovku vpravo)
        start_pos = QPoint(notification.width(), notification.pos().y())
        notification.move(start_pos)
        
        # Cílová pozice
        end_pos = QPoint(0, notification.pos().y())
        
        animation.setStartValue(start_pos)
        animation.setEndValue(end_pos)
        animation.setEasingCurve(QEasingCurve.OutCubic)
        
        # Zajistíme, aby animace nebyla garbage collectována a odstraníme ji po skončení
        animation.finished.connect(lambda: self._remove_animation(animation))
        self.active_animations.append(animation)
        animation.start()
        
    def _animate_notification_out(self, notification):
        """Animuje skrytí notifikace"""
        animation = QPropertyAnimation(notification, b"pos")
        animation.setDuration(300)
        
        # Počáteční pozice
        start_pos = notification.pos()
        
        # Cílová pozice (mimo obrazovku vpravo)
        end_pos = QPoint(notification.width(), notification.pos().y())
        
        animation.setStartValue(start_pos)
        animation.setEndValue(end_pos)
        animation.setEasingCurve(QEasingCurve.OutCubic)
        
        # Po dokončení animace odstranit widget a odstranit animaci ze seznamu
        animation.finished.connect(lambda: self._finalize_notification_removal(notification))
        animation.finished.connect(lambda: self._remove_animation(animation))
        self.active_animations.append(animation)
        animation.start()
        
    def _remove_notification(self, notification):
        """Odstraní notifikaci s animací"""
        if notification in self.notifications:
            self._animate_notification_out(notification)
    
    def _remove_animation(self, animation):
        """Odstraní animaci z aktivních animací"""
        if animation in self.active_animations:
            self.active_animations.remove(animation)
    
    def _finalize_notification_removal(self, notification):
        """Dokončí odstranění notifikace po animaci"""
        if notification in self.notifications:
            self.notifications.remove(notification)
            self.notification_layout.removeWidget(notification)
            notification.deleteLater()
            
            # Pokud nejsou žádné notifikace, skrýt celý widget
            if not self.notifications:
                self.hide()
