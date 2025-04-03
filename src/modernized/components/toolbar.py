from PySide6.QtWidgets import QToolBar, QToolButton, QMenu
from PySide6.QtCore import Signal, QObject, Qt, QSize
from PySide6.QtGui import QIcon, QAction

class ToolbarComponent(QObject):
    # Signals
    theme_toggle_requested = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self._init_toolbar()
        
    def _init_toolbar(self):
        self.toolbar = QToolBar("Nastavení", self.parent)
        self.toolbar.setObjectName("mainToolbar")
        self.toolbar.setMovable(False)
        current_size = self.toolbar.iconSize()
        new_size = QSize(24, 24)  # Alternatively: current_size.scaled(24, 24, Qt.KeepAspectRatio)
        self.toolbar.setIconSize(new_size)
        
        # Theme toggle action
        self.action_toggle_theme = QAction("Přepnout tmavý režim", self.parent)
        self.action_toggle_theme.setObjectName("actionToggleTheme")
        self.action_toggle_theme.triggered.connect(self.theme_toggle_requested.emit)
        self.toolbar.addAction(self.action_toggle_theme)
        
        # Add separator
        self.toolbar.addSeparator()
        
        # Add export button with dropdown menu
        self.export_button = QToolButton(self.parent)
        self.export_button.setObjectName("exportButton")
        self.export_button.setText("Export")
        self.export_button.setPopupMode(QToolButton.InstantPopup)
        
        export_menu = QMenu(self.parent)
        export_menu.setObjectName("exportMenu")
        
        export_png_action = QAction("Export jako PNG", self.parent)
        export_png_action.setObjectName("actionExportPNG")
        export_menu.addAction(export_png_action)
        
        export_jpg_action = QAction("Export jako JPEG", self.parent)
        export_jpg_action.setObjectName("actionExportJPEG")
        export_menu.addAction(export_jpg_action)
        
        export_tiff_action = QAction("Export jako TIFF", self.parent)
        export_tiff_action.setObjectName("actionExportTIFF")
        export_menu.addAction(export_tiff_action)
        self.export_button.setMenu(export_menu)
        
        self.toolbar.addWidget(self.export_button)
        
        # Add help action
        self.action_help = QAction("Nápověda", self.parent)
        self.action_help.setObjectName("actionHelp")
        self.toolbar.addAction(self.action_help)
        
    def update_theme_action_text(self, is_light_theme):
        """Update the text of the theme toggle action based on current theme"""
        if is_light_theme:
            self.action_toggle_theme.setText("Přepnout tmavý režim")
        else:
            self.action_toggle_theme.setText("Přepnout světlý režim")
