
# global_context.py
"""
Globální kontext aplikace sloužící ke sdílení dat mezi různými pluginy.
Můžete sem uložit nastavení, cestu k souborům, nebo jiné společné proměnné,
které mají být přístupné všem modulům v projektu.
"""

global_context = {
    "selected_region": None,         # Aktuálně vybraný region  
    "selected_shapefile": None,      # Cesta k vybranému shapefile (obsahující geometrie regionu)
    "bbox_aligned_extended": None,   # Upravený bounding box (seřazený podle požadavků)
    "bbox_aligned_100": None,        # Nový klíč pro reprojektovaný bounding box s přesností 100
    "vrt_file_path": None,           # Cesta k vytvořenému VRT souboru
    "clipped_vrt_file_path": None,   # Cesta k ořezanému VRT souboru
    "ortofoto_tiles": None,          # Seznam stažených dlaždic
    "ortofoto_region": None,         # Region pro stažené dlaždice
    "ortofoto_output_dir": None,     # Výstupní adresář pro dlaždice z ortofota
    "ortofoto_resolution": None,     # Rozlišení ortofota
    "tiles_output_dir": None,        # Adresář, kde jsou uloženy geotiffové dlaždice
    "final_tiles_dir": None,         # Výstupní adresář pro dlaždice po konečném ořezu
    # Další klíče lze přidat podle potřeb aplikace
}
