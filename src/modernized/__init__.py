# This file makes the modernized directory a Python package
try:
    from .main_window import ModernMainWindow
except ImportError as e:
    print(f"Chyba při importu ModernMainWindow: {e}")
    print("Některé funkce modernizované verze nemusí být dostupné.")

__all__ = ['ModernMainWindow']
