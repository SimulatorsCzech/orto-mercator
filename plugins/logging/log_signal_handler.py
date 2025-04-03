"""
Modul pro zpracování signálů z aplikace a jejich převod na logy.
"""

from plugins.signal_manager import signal_manager
from plugins.logging.log_manager import LogManager

class LogSignalHandler:
    """
    Třída pro zpracování signálů z aplikace a jejich převod na logy.
    """
    
    def __init__(self, log_manager: LogManager):
        """
        Inicializace handleru signálů.
        
        Args:
            log_manager: Správce logů
        """
        self.log_manager = log_manager
        self._connect_signals()
    
    def _connect_signals(self):
        """
        Připojí všechny signály k příslušným slotům pro logování.
        Tato metoda zachytává všechny signály z signal_manager a loguje je.
        """
        # Signály pro změnu regionu
        signal_manager.region_changed.connect(
            lambda region: self.log_manager.add_log("INFO", "RegionManager", f"Region změněn na: {region}")
        )
        
        # Signály pro změnu extenze
        signal_manager.extension_changed.connect(
            lambda value: self.log_manager.add_log("INFO", "BboxPlugin", f"Hodnota extenze změněna na: {value}%")
        )
        
        # Signály pro stahování ortofoto dlaždic
        signal_manager.ortofoto_download_started.connect(
            lambda region: self.log_manager.add_log("INFO", "OrtofotoDownload", f"Zahájeno stahování dlaždic pro region: {region}")
        )
        
        signal_manager.ortofoto_download_progress.connect(
            lambda current, total: self.log_manager.add_log("DEBUG", "OrtofotoDownload", 
                f"Průběh stahování: {current}/{total} ({int(current/total*100 if total > 0 else 0)}%)")
        )
        
        signal_manager.ortofoto_download_finished.connect(
            lambda region, tiles: self.log_manager.add_log("INFO", "OrtofotoDownload", 
                f"Dokončeno stahování dlaždic pro region: {region}, staženo {len(tiles)} dlaždic")
        )
        
        # Signály pro tvorbu VRT vrstvy
        signal_manager.vrt_created.connect(
            lambda vrt_file: self.log_manager.add_log("INFO", "VRTCreation", f"Vytvořena VRT vrstva: {vrt_file}")
        )
        
        # Signály pro ořezání podle shapefile
        signal_manager.shapefile_clip_finished.connect(
            lambda clipped_file: self.log_manager.add_log("INFO", "ShapefileClip", f"Dokončeno ořezání podle shapefile: {clipped_file}")
        )
        
        # Signály pro reprojekci
        signal_manager.reprojection_finished.connect(
            lambda reprojected_file: self.log_manager.add_log("INFO", "Reprojection", f"Dokončena reprojekce: {reprojected_file}")
        )
        
        # Signály pro rozdělení na dlaždice
        signal_manager.tiling_finished.connect(
            lambda output_dir, tile_count: self.log_manager.add_log("INFO", "Tiling", 
                f"Dokončeno rozdělení na dlaždice: {tile_count} dlaždic v adresáři {output_dir}")
        )
        
        # Signály pro chyby
        signal_manager.processing_error.connect(
            lambda error_message: self.log_manager.add_log("ERROR", "Processing", f"Chyba zpracování: {error_message}")
        )
        
        # Signály pro aktualizaci globálního kontextu
        signal_manager.global_context_updated.connect(
            lambda context: self.log_manager.add_log("DEBUG", "GlobalContext", f"Aktualizován globální kontext: {str(context)}")
        )