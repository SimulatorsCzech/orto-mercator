# signal_manager.py
"""
Signal Manager slouží jako centralizovaný objekt obsahující signály,
které pluginy odesílají nebo přijímají pro vzájemnou komunikaci.
Tento modul využívá PySide6.QtCore.Signal a QObject pro definici signálů.
"""

from PySide6.QtCore import QObject, Signal

class SignalManager(QObject):
    # Signály pro stahování ortofoto dlaždic
    ortofoto_download_started = Signal(str)  # Např. název regionu
    ortofoto_download_progress = Signal(int, int)  # (aktuální dlaždice, celkem dlaždic)
    ortofoto_download_finished = Signal(str, list)  # (region, seznam dlaždic)
    
    # Signály pro ořezávání shapefile
    shapefile_clip_finished = Signal(str)  # (cesta k ořezanému souboru)
    
    # Signály pro tvorbu VRT a dělení na dlaždice
    vrt_created = Signal(str)  # (cesta k VRT souboru)
    tiling_finished = Signal(str, int)  # (adresář, počet dlaždic)
    
    # Signál pro reprojekci – vyžadovaný například pluginem Logování
    reprojection_finished = Signal(str)  # (cesta k reprojektovanému souboru)
    
    # Signál pro chybová hlášení při zpracování
    processing_error = Signal(str)
    
    # Signál pro změnu regionu
    region_changed = Signal(str)  # nový vybraný region
    
    # Signál pro změnu rozsahu (extension) – předává aktualizovanou hodnotu extension
    extension_changed = Signal(str)
    
    # NOVĚ PŘIDANÝ SIGNÁL: global_context_updated – vysílá aktuální global_context jako slovník
    global_context_updated = Signal(dict)

# Vytvoříme jednu globální instanci SignalManager, kterou budou pluginy sdílet.
signal_manager = SignalManager()