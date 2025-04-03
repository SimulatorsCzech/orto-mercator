from PySide6.QtWidgets import QStatusBar, QProgressBar, QLabel, QHBoxLayout, QWidget
from PySide6.QtCore import Qt, QTimer, Signal, QObject

class StatusPanelComponent(QObject):
    """Pokročilý stavový panel s indikátorem průběhu a systémem notifikací"""
    
    # Signály
    notification_shown = Signal(str, int)  # zpráva, typ (0=info, 1=varování, 2=chyba)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self._init_ui()
        
    def _init_ui(self):
        # Vytvoření status baru
        self.status_bar = QStatusBar(self.parent)
        self.parent.setStatusBar(self.status_bar)
        
        # Vytvoření widgetu pro obsah status baru
        self.status_content = QWidget()
        status_layout = QHBoxLayout(self.status_content)
        status_layout.setContentsMargins(0, 0, 0, 0)
        
        # Přidání indikátoru průběhu
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setMaximumWidth(150)
        self.progress_bar.setVisible(False)
        status_layout.addWidget(self.progress_bar)
        
        # Přidání stavového textu
        self.status_label = QLabel("Připraveno")
        status_layout.addWidget(self.status_label, 1)
        
        # Přidání informace o verzi
        self.version_label = QLabel("v1.0.0")
        self.version_label.setAlignment(Qt.AlignRight)
        status_layout.addWidget(self.version_label)
        
        # Přidání obsahu do status baru
        self.status_bar.addWidget(self.status_content, 1)
        
        # Timer pro automatické skrytí notifikací
        self.notification_timer = QTimer(self)
        self.notification_timer.setSingleShot(True)
        self.notification_timer.timeout.connect(self._clear_notification)
        
    def show_message(self, message, timeout=3000):
        """Zobrazí zprávu ve stavovém řádku"""
        self.status_label.setText(message)
        self.notification_shown.emit(message, 0)
        
        # Automatické vyčištění po timeoutu
        if timeout > 0:
            self.notification_timer.start(timeout)
            
    def show_warning(self, message, timeout=5000):
        """Zobrazí varování ve stavovém řádku"""
        self.status_label.setText("⚠️ " + message)
        self.status_label.setStyleSheet("color: #FF9800;")
        self.notification_shown.emit(message, 1)
        
        # Automatické vyčištění po timeoutu
        if timeout > 0:
            self.notification_timer.start(timeout)
            
    def show_error(self, message, timeout=7000):
        """Zobrazí chybu ve stavovém řádku"""
        self.status_label.setText("❌ " + message)
        self.status_label.setStyleSheet("color: #F44336;")
        self.notification_shown.emit(message, 2)
        
        # Automatické vyčištění po timeoutu
        if timeout > 0:
            self.notification_timer.start(timeout)
    
    def _clear_notification(self):
        """Vyčistí notifikaci a vrátí výchozí styl"""
        self.status_label.setText("Připraveno")
        self.status_label.setStyleSheet("")
        
    def show_progress(self, value=None):
        """Zobrazí nebo aktualizuje indikátor průběhu"""
        if value is None:
            # Neurčitý průběh (čekání)
            self.progress_bar.setRange(0, 0)
        else:
            # Určitý průběh (0-100%)
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(value)
            
        self.progress_bar.setVisible(True)
        
    def hide_progress(self):
        """Skryje indikátor průběhu"""
        self.progress_bar.setVisible(False)
        
    def set_version(self, version):
        """Nastaví zobrazovanou verzi aplikace"""
        self.version_label.setText(f"v{version}")