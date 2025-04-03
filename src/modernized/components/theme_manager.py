from PySide6.QtCore import QObject, Signal

class ThemeManager(QObject):
    # Signal emitted when theme changes (True = light, False = dark)
    theme_changed = Signal(bool)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self._is_light_theme = True
    
    @property
    def is_light_theme(self):
        return self._is_light_theme
        
    @is_light_theme.setter
    def is_light_theme(self, value):
        self._is_light_theme = value
        self.theme_changed.emit(value)
        
    def apply_theme(self, light=True):
        """Apply light or dark theme to the application"""
        self.is_light_theme = light
        
        if light:
            self.parent.setStyleSheet("""
                QMainWindow { background-color: #f9f9f9; }
                QListWidget { 
                    background: #ffffff; 
                    border: 1px solid #cccccc; 
                    font-size: 16px; 
                    padding: 5px;
                    border-radius: 4px;
                }
                QListWidget::item { 
                    padding: 8px;
                    margin: 2px 0;
                    border-radius: 4px;
                }
                QListWidget::item:selected { 
                    background: #e0f0ff; 
                    color: #0066cc;
                }
                QListWidget::item:hover { 
                    background: #f0f0f0; 
                }
                QStackedWidget { 
                    background: #ffffff; 
                    border: 1px solid #cccccc;
                    border-radius: 4px;
                }
                QToolBar { 
                    background: #eaeaea; 
                    border-bottom: 1px solid #cccccc;
                    spacing: 5px;
                }
                QToolButton {
                    background: #f5f5f5;
                    border: 1px solid #cccccc;
                    border-radius: 4px;
                    padding: 4px;
                }
                QToolButton:hover {
                    background: #e0e0e0;
                }
                QLineEdit { 
                    background: #ffffff; 
                    border: 1px solid #cccccc; 
                    padding: 8px;
                    border-radius: 4px;
                }
                QStatusBar { 
                    background: #eaeaea; 
                    border-top: 1px solid #cccccc;
                }
                QSplitter::handle {
                    background: #cccccc;
                }
                QScrollBar {
                    background: #f0f0f0;
                    width: 12px;
                }
                QScrollBar::handle {
                    background: #cccccc;
                    border-radius: 6px;
                }
                QScrollBar::handle:hover {
                    background: #aaaaaa;
                }
                QTabWidget::pane {
                    border: 1px solid #cccccc;
                    border-radius: 4px;
                }
                QTabBar::tab {
                    background: #f0f0f0;
                    border: 1px solid #cccccc;
                    border-bottom-color: #cccccc;
                    border-top-left-radius: 4px;
                    border-top-right-radius: 4px;
                    padding: 6px 10px;
                }
                QTabBar::tab:selected {
                    background: #ffffff;
                    border-bottom-color: #ffffff;
                }
                QTabBar::tab:hover {
                    background: #e0e0e0;
                }
                QPushButton {
                    background: #f5f5f5;
                    border: 1px solid #cccccc;
                    border-radius: 4px;
                    padding: 6px 12px;
                }
                QPushButton:hover {
                    background: #e0e0e0;
                }
                QPushButton:pressed {
                    background: #d0d0d0;
                }
                QComboBox {
                    background: #ffffff;
                    border: 1px solid #cccccc;
                    border-radius: 4px;
                    padding: 4px 8px;
                }
                QComboBox:hover {
                    border-color: #aaaaaa;
                }
                QComboBox::drop-down {
                    subcontrol-origin: padding;
                    subcontrol-position: top right;
                    width: 20px;
                    border-left: 1px solid #cccccc;
                }
            """)
        else:
            self.parent.setStyleSheet("""
                QMainWindow { 
                    background-color: #2b2b2b; 
                    color: #e0e0e0; 
                }
                QListWidget { 
                    background: #3c3f41; 
                    border: 1px solid #555555; 
                    color: #e0e0e0; 
                    font-size: 16px; 
                    padding: 5px;
                    border-radius: 4px;
                }
                QListWidget::item { 
                    padding: 8px;
                    margin: 2px 0;
                    border-radius: 4px;
                }
                QListWidget::item:selected { 
                    background: #2d5a88; 
                    color: #ffffff;
                }
                QListWidget::item:hover { 
                    background: #4c4c4c; 
                }
                QStackedWidget { 
                    background: #3c3f41; 
                    border: 1px solid #555555;
                    border-radius: 4px;
                }
                QToolBar { 
                    background: #3c3f41; 
                    border-bottom: 1px solid #555555;
                    spacing: 5px;
                }
                QToolButton {
                    background: #4c4c4c;
                    border: 1px solid #555555;
                    border-radius: 4px;
                    padding: 4px;
                    color: #e0e0e0;
                }
                QToolButton:hover {
                    background: #5a5a5a;
                }
                QLineEdit { 
                    background: #555555; 
                    border: 1px solid #777777; 
                    padding: 8px;
                    color: #e0e0e0;
                    border-radius: 4px;
                }
                QStatusBar { 
                    background: #3c3f41; 
                    border-top: 1px solid #555555;
                    color: #e0e0e0;
                }
                QSplitter::handle {
                    background: #555555;
                }
                QScrollBar {
                    background: #3c3f41;
                    width: 12px;
                }
                QScrollBar::handle {
                    background: #555555;
                    border-radius: 6px;
                }
                QScrollBar::handle:hover {
                    background: #777777;
                }
                QTabWidget::pane {
                    border: 1px solid #555555;
                    border-radius: 4px;
                }
                QTabBar::tab {
                    background: #3c3f41;
                    border: 1px solid #555555;
                    border-bottom-color: #555555;
                    border-top-left-radius: 4px;
                    border-top-right-radius: 4px;
                    padding: 6px 10px;
                    color: #e0e0e0;
                }
                QTabBar::tab:selected {
                    background: #4c4c4c;
                    border-bottom-color: #4c4c4c;
                }
                QTabBar::tab:hover {
                    background: #5a5a5a;
                }
                QPushButton {
                    background: #4c4c4c;
                    border: 1px solid #555555;
                    border-radius: 4px;
                    padding: 6px 12px;
                    color: #e0e0e0;
                }
                QPushButton:hover {
                    background: #5a5a5a;
                }
                QPushButton:pressed {
                    background: #666666;
                }
                QComboBox {
                    background: #4c4c4c;
                    border: 1px solid #555555;
                    border-radius: 4px;
                    padding: 4px 8px;
                    color: #e0e0e0;
                }
                QComboBox:hover {
                    border-color: #777777;
                }
                QComboBox::drop-down {
                    subcontrol-origin: padding;
                    subcontrol-position: top right;
                    width: 20px;
                    border-left: 1px solid #555555;
                }
                QLabel {
                    color: #e0e0e0;
                }
                QCheckBox {
                    color: #e0e0e0;
                }
                QRadioButton {
                    color: #e0e0e0;
                }
                QSpinBox {
                    background: #4c4c4c;
                    border: 1px solid #555555;
                    border-radius: 4px;
                    padding: 4px;
                    color: #e0e0e0;
                }
                QGroupBox {
                    color: #e0e0e0;
                    border: 1px solid #555555;
                    border-radius: 4px;
                    margin-top: 1ex;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    subcontrol-position: top left;
                    padding: 0 3px;
                }
            """)
    
    def toggle_theme(self):
        """Toggle between light and dark themes"""
        self.apply_theme(not self.is_light_theme)
