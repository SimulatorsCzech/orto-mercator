#!/usr/bin/env python3
"""
Skript pro vytvoření symbolických odkazů na shapefile soubory.

Tento skript vytvoří symbolické odkazy na shapefile soubory s mezerami v názvech.
"""

import os
import logging
import sys

# Konfigurování logování
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def create_symlinks(shapefile_dir):
    """
    Vytvoří symbolické odkazy na shapefile soubory s mezerami v názvech.
    
    Args:
        shapefile_dir (str): Adresář s shapefile soubory
    """
    if not os.path.exists(shapefile_dir):
        logger.error(f"Adresář {shapefile_dir} neexistuje")
        return
    
    # Mapování názvů souborů
    name_mapping = {
        "HlavnimestoPraha-Kraj": "Hlavní město Praha-Kraj",
        "Karlovarskykraj-Kraj": "Karlovarský kraj-Kraj",
        "Kralovehradeckykraj-Kraj": "Královéhradecký kraj-Kraj",
        "Libereckykraj-Kraj": "Liberecký kraj-Kraj",
        "Olomouckykraj-Kraj": "Olomoucký kraj-Kraj",
        "Plzenskykraj-Kraj": "Plzeňský kraj-Kraj"
    }
    
    # Vytvoření symbolických odkazů
    for file in os.listdir(shapefile_dir):
        for old_name, new_name in name_mapping.items():
            if file.startswith(old_name):
                extension = file.split(".")[-1]
                old_path = os.path.join(shapefile_dir, file)
                new_path = os.path.join(shapefile_dir, f"{new_name}.{extension}")
                
                # Kontrola, zda již symbolický odkaz existuje
                if os.path.exists(new_path):
                    logger.info(f"Symbolický odkaz {new_path} již existuje")
                    continue
                
                try:
                    # Vytvoření symbolického odkazu
                    if sys.platform == "win32":
                        # Na Windows je potřeba administrátorská práva nebo speciální nastavení
                        import ctypes
                        kdll = ctypes.windll.LoadLibrary("kernel32.dll")
                        kdll.CreateSymbolicLinkW(new_path, old_path, 0)
                    else:
                        # Na Linuxu a macOS
                        os.symlink(old_path, new_path)
                    
                    logger.info(f"Vytvořen symbolický odkaz: {new_path} -> {old_path}")
                except Exception as e:
                    logger.error(f"Chyba při vytváření symbolického odkazu {new_path}: {str(e)}")

if __name__ == "__main__":
    # Adresář s shapefile soubory
    shapefile_dir = os.path.join("data", "shapefile")
    
    # Vytvoření symbolických odkazů
    create_symlinks(shapefile_dir)