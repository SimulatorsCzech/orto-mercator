from PySide6.QtWidgets import QWidget, QVBoxLayout, QStackedWidget, QLabel
from PySide6.QtCore import QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QAction
from .zoomable_view import ZoomableGraphicsView

class ContentPanelComponent(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self._init_ui()
        
    def _init_ui(self):
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # Plugin content stack
        self.plugin_stack = QStackedWidget(self)
        
        # Preview area
        self.preview_view = ZoomableGraphicsView(self)
        self.preview_view.setMinimumHeight(300)
        
        # Add header label for preview
        preview_label = QLabel("Náhled", self)
        
        # Add widgets to layout
        layout.addWidget(self.plugin_stack, 3)
        layout.addWidget(preview_label)
        layout.addWidget(self.preview_view, 1)
        
        # Set layout
        self.setLayout(layout)
        
    def setup_plugin_stack(self, plugins):
        """Set up the plugin stack with plugin UIs"""
        self.plugins = plugins
        
        # Clear existing widgets
        while self.plugin_stack.count() > 0:
            self.plugin_stack.removeWidget(self.plugin_stack.widget(0))
            
        # Add plugin widgets to stack
        for plugin in plugins:
            self.plugin_stack.addWidget(plugin.setup_ui(self.parent))
    
    def switch_to_plugin(self, index):
        """Switch to the specified plugin with animation"""
        if index < 0 or index >= self.plugin_stack.count():
            return
            
        current_widget = self.plugin_stack.currentWidget()
        new_widget = self.plugin_stack.widget(index)
        
        # Animate transition
        self._fade_transition(current_widget, new_widget)
        self.plugin_stack.setCurrentIndex(index)
    
    def _fade_transition(self, old_widget, new_widget):
        """Create a fade transition between widgets"""
        animation = QPropertyAnimation(new_widget, b"windowOpacity")
        animation.setDuration(300)
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.InOutQuad)
        new_widget.setWindowOpacity(0.0)
        animation.start()
