import sys
import os
import logging

# Add parent directory to sys.path for module imports
current_dir = os.path.abspath(os.path.dirname(__file__))
parent_dir = os.path.dirname(os.path.dirname(current_dir))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

try:
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QCoreApplication, Qt
    from PySide6.QtQuick import QQuickWindow, QSGRendererInterface
    from PySide6.QtGui import QAction  # Added QAction for potential use

    # Set attributes before creating QApplication
    QCoreApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
    QQuickWindow.setGraphicsApi(QSGRendererInterface.OpenGLRhi)

    from .main_window import ModernMainWindow
except ImportError as e:
    print(f"Import error: {e}")
    print("Make sure you have PySide6 library installed.")
    print("You can install it using: pip install PySide6")
    sys.exit(1)

# Configure logging
def setup_logging():
    """Set up application logging"""
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        handlers=[
            logging.FileHandler("app.log"),
            logging.StreamHandler()
        ]
    )
    
    # Suppress some unnecessary logs
    logging.getLogger("PIL").setLevel(logging.WARNING)
    
    logger = logging.getLogger(__name__)
    logger.info("Application starting...")
    
    return logger

def main():
    """Main application function"""
    # Set up logging
    logger = setup_logging()
    
    try:
        # Create application
        app = QApplication(sys.argv)
        app.setApplicationName("Orto Pokrokové")
        app.setOrganizationName("OrtoPokrokove")
        app.setOrganizationDomain("ortopokrokove.cz")
        
        # Set application style
        app.setStyle("Fusion")
        
        # Create main window
        win = ModernMainWindow()
        win.show()
        
        # Run application
        logger.info("Application started")
        sys.exit(app.exec())
        
    except Exception as e:
        logger.error(f"Critical error during application startup: {str(e)}", exc_info=True)
        raise

if __name__ == '__main__':
    main()
