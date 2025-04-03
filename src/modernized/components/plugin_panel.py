from PySide6.QtWidgets import QWidget, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem, QLabel
from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtGui import QFont

class PluginPanelComponent(QWidget):
    # Signals
    plugin_selected = Signal(int, object)  # index, plugin
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        
    def _init_ui(self):
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # Header label
        header_label = QLabel("Dostupné pluginy", self)
        header_label.setFont(QFont("Segoe UI", 14, QFont.Bold))
        layout.addWidget(header_label)
        
        # Search field
        self.search_edit = QLineEdit(self)
        self.search_edit.setPlaceholderText("Vyhledat plugin...")
        self.search_edit.textChanged.connect(self._filter_plugins)
        layout.addWidget(self.search_edit)
        
        # Plugin list
        self.plugin_list = QListWidget(self)
        self.plugin_list.setFont(QFont("Segoe UI", 12))
        self.plugin_list.currentRowChanged.connect(self._on_plugin_selected)
        layout.addWidget(self.plugin_list)
        
        # Set layout
        self.setLayout(layout)
        
    def add_plugins(self, plugins):
        """Add plugins to the list widget"""
        self.plugins = plugins
        self.plugin_list.clear()
        
        for plugin in plugins:
            item = QListWidgetItem(plugin.name())
            item.setData(Qt.UserRole, plugin)
            self.plugin_list.addItem(item)
    
    def _filter_plugins(self, text):
        """Filter plugins based on search text"""
        for index in range(self.plugin_list.count()):
            item = self.plugin_list.item(index)
            if text.lower() in item.text().lower():
                item.setHidden(False)
            else:
                item.setHidden(True)
    
    def _on_plugin_selected(self, index):
        """Handle plugin selection"""
        if index < 0 or index >= self.plugin_list.count():
            return
            
        plugin = self.plugin_list.item(index).data(Qt.UserRole)
        self.plugin_selected.emit(index, plugin)