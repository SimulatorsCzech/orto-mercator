from PySide6.QtWidgets import QGraphicsView, QGraphicsScene
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QPainter, QWheelEvent

class ZoomableGraphicsView(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Set up the view
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        
        # Initialize scene
        self.setScene(QGraphicsScene(self))
        
        # Set background
        self.setStyleSheet("background-color: #333;")
        
        # Initialize zoom level
        self._zoom = 0
        self._max_zoom = 20
        self._min_zoom = -10
        self._zoom_factor_base = 1.25
        
    def wheelEvent(self, event: QWheelEvent):
        """Handle mouse wheel events for zooming"""
        if event.modifiers() & Qt.ControlModifier:
            # Zoom with Ctrl+Wheel
            angle_delta = event.angleDelta().y()
            
            if angle_delta > 0:
                zoom_factor = self._zoom_factor_base
                self._zoom += 1
            else:
                zoom_factor = 1 / self._zoom_factor_base
                self._zoom -= 1
                
            # Limit zoom level
            if self._zoom < self._min_zoom:
                self._zoom = self._min_zoom
                return
            if self._zoom > self._max_zoom:
                self._zoom = self._max_zoom
                return
                
            # Apply zoom
            self.scale(zoom_factor, zoom_factor)
        else:
            # Normal scrolling
            super().wheelEvent(event)
            
    def reset_zoom(self):
        """Reset zoom to original level"""
        self.resetTransform()
        self._zoom = 0
        
    def fit_in_view(self):
        """Fit the entire scene in the view"""
        self.fitInView(self.scene().sceneRect(), Qt.KeepAspectRatio)
        # Adjust zoom level based on current transform
        self._zoom = 0  # Reset zoom counter