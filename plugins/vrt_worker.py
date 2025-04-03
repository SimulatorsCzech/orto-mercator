"""
Vylepšený worker pro tvorbu VRT vrstvy s lepší správou vláken a průběžnými aktualizacemi.
Poskytuje odhad zbývajícího času a detailnější informace o průběhu zpracování.
"""

import os
import time
import logging
import gc
from typing import List, Dict, Optional, Tuple, Any
from concurrent.futures import ThreadPoolExecutor, as_completed, Future, TimeoutError
from datetime import datetime, timedelta

from PySide6.QtCore import QThread, Signal

from osgeo import gdal
import numpy as np
from PIL import Image

# Nastavení loggeru
logger = logging.getLogger("VRTCreation")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

def sanitize_filename(name: str) -> str:
    """
    Sanitizuje řetězec pro použití v názvu souboru.
    """
    import unicodedata
    import re
    # Převede diakritiku a další speciální znaky na odpovídající ASCII verze.
    normalized = unicodedata.normalize('NFKD', name).encode('ASCII', 'ignore').decode('ASCII')
    # Nahrazení mezer pomlčkami
    normalized = normalized.replace(" ", "-")
    # Odstraní ostatní nepovolené znaky, ponechá jen písmena, čísla, podtržítka a pomlčky.
    return re.sub(r'[^A-Za-z0-9_-]', '', normalized)

def map_resampling_method(method: str) -> str:
    """
    Převede název metody resamplingu na hodnotu podporovanou GDAL.
    Pokud je metoda "nearest", vrátí "near", jinak vrátí původní hodnotu.
    """
    method = method.lower().strip()
    if method == "nearest":
        return "near"
    return method

def read_vsifile(filepath: str) -> bytes:
    """
    Otevře soubor z /vsimem/ a načte celý jeho obsah.
    """
    fp = gdal.VSIFOpenL(filepath, "rb")
    if fp is None:
        raise Exception(f"Nelze otevřít {filepath} pro čtení.")
    # Přesun na konec a zjištění velikosti
    gdal.VSIFSeekL(fp, 0, 2)
    filesize = gdal.VSIFTellL(fp)
    gdal.VSIFSeekL(fp, 0, 0)
    data = gdal.VSIFReadL(1, filesize, fp)
    gdal.VSIFCloseL(fp)
    return data

class TileProcessingStatus:
    """Třída pro sledování stavu zpracování dlaždic"""
    def __init__(self, total_tiles: int):
        self.total_tiles = total_tiles
        self.processed_tiles = 0
        self.successful_tiles = 0
        self.failed_tiles = 0
        self.start_time = time.time()
        self.last_update_time = time.time()
        self.estimated_completion_time = None
        self.processing_speed = 0  # dlaždice za sekundu
    
    def update(self, success: bool) -> Dict[str, Any]:
        """Aktualizuje stav zpracování a vrací informace o průběhu"""
        self.processed_tiles += 1
        if success:
            self.successful_tiles += 1
        else:
            self.failed_tiles += 1
        
        current_time = time.time()
        elapsed_time = current_time - self.start_time
        
        # Aktualizace rychlosti zpracování každých 5 sekund nebo 10 dlaždic
        if (current_time - self.last_update_time > 5 or 
            self.processed_tiles % 10 == 0) and self.processed_tiles > 0:
            self.processing_speed = self.processed_tiles / max(1, elapsed_time)
            self.last_update_time = current_time
        
        # Odhad zbývajícího času
        if self.processing_speed > 0:
            remaining_tiles = self.total_tiles - self.processed_tiles
            remaining_seconds = remaining_tiles / self.processing_speed
            self.estimated_completion_time = datetime.now() + timedelta(seconds=remaining_seconds)
        
        return {
            "processed": self.processed_tiles,
            "successful": self.successful_tiles,
            "failed": self.failed_tiles,
            "total": self.total_tiles,
            "percent": (self.processed_tiles / self.total_tiles) * 100 if self.total_tiles > 0 else 0,
            "elapsed_seconds": elapsed_time,
            "processing_speed": self.processing_speed,
            "estimated_completion": self.estimated_completion_time
        }

class VRTCreationWorker(QThread):
    """
    Vylepšený worker pro tvorbu VRT vrstvy s lepší správou vláken a průběžnými aktualizacemi.
    """
    progress_updated = Signal(int, int, dict)  # (aktuální krok, celkem kroků, další informace)
    status_message = Signal(str)               # Informační zpráva o průběhu
    vrt_created = Signal(str)                  # Cesta ke VRT souboru
    creation_error = Signal(str)               # Chybová zpráva
    
    # Timeout pro jednotlivou konverzi (v sekundách)
    TILE_CONVERSION_TIMEOUT = 600
    
    def __init__(self, tiles: List[str], output_file: str, options: Dict[str, any] = None):
        super().__init__()
        self.tiles = tiles
        self.output_file = output_file
        self.options = options or {}
        self.is_running = True
        self.status = TileProcessingStatus(len(tiles))
        
        # Nastavení maximálního počtu vláken
        self.max_workers = min(
            self.options.get("max_workers", os.cpu_count() or 4),
            len(self.tiles) if self.tiles else 1
        )
        
        # Nastavení velikosti dávky pro zpracování
        self.batch_size = self.options.get("batch_size", 100)
        
        logger.info(f"Inicializován VRTCreationWorker s {len(tiles)} dlaždicemi, max_workers={self.max_workers}, batch_size={self.batch_size}")

    def stop(self):
        """Zastaví vytvoření VRT vrstvy."""
        logger.info("Požadavek na zastavení zpracování VRT")
        self.is_running = False
        self.status_message.emit("Zastavuji zpracování...")

    def cleanup_memory(self):
        """Explicitně uvolní paměť a spustí garbage collector"""
        # Uvolnění všech GDAL datasetů v paměti
        gdal.GDALDestroyDriverManager()
        
        # Explicitní spuštění garbage collectoru
        gc.collect()
        
        logger.debug("Provedeno uvolnění paměti a garbage collection")
    
    def convert_tile(self, tile: str) -> Optional[str]:
        """
        Převede jeden PNG soubor na GeoTIFF se CRS EPSG:3857, provede volitelný downscale, 
        barevnou korekci a reprojekci do EPSG:4326.
        Všechny kroky se provádějí v paměti pomocí GDAL /vsimem/ a na disku bude vytvořen pouze finální TIFF.
        Vrací cestu k finálnímu TIFF s reprojekcí nebo None.
        """
        max_attempts = self.options.get("max_tile_conversion_attempts", 3)
        attempt = 0
        
        while attempt < max_attempts:
            try:
                # Vytvoříme sanitizovaný základní identifikátor pro /vsimem/ soubory
                base_name = os.path.splitext(os.path.basename(tile))[0]
                base_name = sanitize_filename(base_name)
                mem_prefix = f"/vsimem/{base_name}"
                
                # 1) Konverze PNG -> GeoTIFF (EPSG:3857) pomocí GDAL Translate
                translate_options = gdal.TranslateOptions(format="GTiff", outputSRS="EPSG:3857")
                ds_3857 = gdal.Translate(mem_prefix + "_merc.tif", tile, options=translate_options)
                if ds_3857 is None:
                    raise Exception(f"Konverze {tile} do GeoTIFF selhala.")
                ds_3857 = None  # Zavřeme dataset – soubor je v /vsimem/
                
                # 2) Kontrola počtu kanálů; pokud je méně než 4, přidáme alfa kanál
                ds_temp = gdal.Open(mem_prefix + "_merc.tif")
                if ds_temp is None:
                    raise Exception("Nelze otevřít GDAL dataset z /vsimem/ po konverzi.")
                band_count = ds_temp.RasterCount
                ds_temp = None
                if band_count < 4:
                    warp_opts_alpha = gdal.WarpOptions(format="GTiff", dstAlpha=True)
                    ds_alpha = gdal.Warp(mem_prefix + "_merc_alpha.tif", mem_prefix + "_merc.tif", options=warp_opts_alpha)
                    if ds_alpha is None:
                        raise Exception("Přidání alfa kanálu selhalo.")
                    ds_alpha = None
                    # Přepíšeme původní soubor v paměti
                    buffer = read_vsifile(mem_prefix + "_merc_alpha.tif")
                    gdal.Unlink(mem_prefix + "_merc.tif")
                    gdal.FileFromMemBuffer(mem_prefix + "_merc.tif", buffer)
                    gdal.Unlink(mem_prefix + "_merc_alpha.tif")
                
                # 3) Volitelný downscale, pokud je zadán
                if self.options.get("downscale"):
                    downscale_val = float(self.options["downscale"])
                    downscale_method = map_resampling_method(self.options.get("downscale_resampling", "lanczos"))
                    warp_opts_downscale = gdal.WarpOptions(format="GTiff",
                                                           xRes=downscale_val,
                                                           yRes=downscale_val,
                                                           resampleAlg=downscale_method)
                    ds_downscaled = gdal.Warp(mem_prefix + "_merc_ds.tif", mem_prefix + "_merc.tif", options=warp_opts_downscale)
                    if ds_downscaled is None:
                        raise Exception("Downscale selhal.")
                    ds_downscaled = None
                    # Přepíšeme původní dataset v paměti
                    buffer = read_vsifile(mem_prefix + "_merc_ds.tif")
                    gdal.Unlink(mem_prefix + "_merc.tif")
                    gdal.FileFromMemBuffer(mem_prefix + "_merc.tif", buffer)
                    gdal.Unlink(mem_prefix + "_merc_ds.tif")
                
                # 4) Aplikace barevné korekce, pokud je nastavena
                color_correction = self.options.get("color_correction")
                if color_correction and (color_correction.brightness != 1.0 or 
                                         color_correction.contrast != 1.0 or 
                                         color_correction.saturation != 1.0 or 
                                         color_correction.gamma != 1.0):
                    # Načtení datasetu do PIL Image
                    ds_temp = gdal.Open(mem_prefix + "_merc.tif")
                    if ds_temp is None:
                        raise Exception("Nelze otevřít dataset pro barevnou korekci.")
                    
                    # Převod GDAL datasetu na PIL Image
                    width = ds_temp.RasterXSize
                    height = ds_temp.RasterYSize
                    bands = ds_temp.RasterCount
                    
                    # Načtení dat z jednotlivých pásem
                    if bands == 4:  # RGBA
                        r_band = ds_temp.GetRasterBand(1).ReadAsArray()
                        g_band = ds_temp.GetRasterBand(2).ReadAsArray()
                        b_band = ds_temp.GetRasterBand(3).ReadAsArray()
                        a_band = ds_temp.GetRasterBand(4).ReadAsArray()
                        img_array = np.stack((r_band, g_band, b_band, a_band), axis=2)
                    else:  # RGB nebo jiný počet pásem
                        r_band = ds_temp.GetRasterBand(1).ReadAsArray()
                        g_band = ds_temp.GetRasterBand(2).ReadAsArray()
                        b_band = ds_temp.GetRasterBand(3).ReadAsArray()
                        img_array = np.stack((r_band, g_band, b_band), axis=2)
                    
                    ds_temp = None  # Zavřeme dataset
                    
                    # Vytvoření PIL Image
                    if bands == 4:
                        pil_img = Image.fromarray(img_array, 'RGBA')
                    else:
                        pil_img = Image.fromarray(img_array, 'RGB')
                    
                    # Aplikace barevné korekce
                    corrected_img = color_correction.apply_to_image(pil_img)
                    
                    # Převod zpět na numpy array
                    corrected_array = np.array(corrected_img)
                    
                    # Vytvoření nového GDAL datasetu s korigovanými daty
                    driver = gdal.GetDriverByName('GTiff')
                    color_corrected_ds = driver.Create(mem_prefix + "_color_corrected.tif", 
                                                      width, height, bands, gdal.GDT_Byte)
                    
                    # Zápis dat do jednotlivých pásem
                    for i in range(bands):
                        band = color_corrected_ds.GetRasterBand(i+1)
                        band.WriteArray(corrected_array[:, :, i])
                    
                    # Kopírování georeference
                    ds_temp = gdal.Open(mem_prefix + "_merc.tif")
                    color_corrected_ds.SetGeoTransform(ds_temp.GetGeoTransform())
                    color_corrected_ds.SetProjection(ds_temp.GetProjection())
                    ds_temp = None
                    
                    # Uložení a zavření datasetu
                    color_corrected_ds.FlushCache()
                    color_corrected_ds = None
                    
                    # Přepíšeme původní dataset korigovaným
                    buffer = read_vsifile(mem_prefix + "_color_corrected.tif")
                    gdal.Unlink(mem_prefix + "_merc.tif")
                    gdal.FileFromMemBuffer(mem_prefix + "_merc.tif", buffer)
                    gdal.Unlink(mem_prefix + "_color_corrected.tif")
                
                # 5) Reprojekce do WGS84 (EPSG:4326)
                ds_temp = gdal.Open(mem_prefix + "_merc.tif")
                if ds_temp is None:
                    raise Exception("Nelze otevřít dataset v paměti pro reprojekci.")
                input_width = ds_temp.RasterXSize
                input_height = ds_temp.RasterYSize
                ds_temp = None
                nodata = self.options.get("nodata")
                warp_opts_reproj = gdal.WarpOptions(format="GTiff",
                                                    dstSRS="EPSG:4326",
                                                    srcSRS="EPSG:3857",
                                                    resampleAlg=map_resampling_method(self.options.get("resampling", "nearest")),
                                                    width=input_width,
                                                    height=input_height,
                                                    dstNodata=nodata if nodata is not None else None)
                ds_wgs84 = gdal.Warp(mem_prefix + "_wgs84.tif", mem_prefix + "_merc.tif", options=warp_opts_reproj)
                if ds_wgs84 is None:
                    raise Exception("Reprojekce selhala.")
                ds_wgs84 = None
                
                # Volitelně smažeme mezivýstup Mercator dataset z paměti
                if self.options.get("delete_mercator", False):
                    gdal.Unlink(mem_prefix + "_merc.tif")
                
                # Finální výstup uložíme z /vsimem/ na disk
                ds_final = gdal.Open(mem_prefix + "_wgs84.tif")
                if ds_final is None:
                    raise Exception("Nelze otevřít reprojektovaný dataset.")
                driver = gdal.GetDriverByName("GTiff")
                # Získáme původní název, sanitizujeme pouze základ
                original_basename = os.path.basename(tile)
                base, _ = os.path.splitext(original_basename)
                base = sanitize_filename(base)
                out_tile = os.path.join(os.path.dirname(tile), f"{base}_wgs84.tif")
                driver.CreateCopy(out_tile, ds_final)
                ds_final = None
                
                # Uvolníme paměťový soubor
                gdal.Unlink(mem_prefix + "_wgs84.tif")
                
                # Volitelně smažeme původní PNG
                if self.options.get("delete_png", False):
                    try:
                        os.remove(tile)
                    except Exception as e:
                        logger.warning(f"Nelze smazat původní PNG {tile}: {e}")
                
                # Explicitní uvolnění paměti po zpracování dlaždice
                self.cleanup_memory()
                
                return out_tile
            except Exception as e:
                logger.error(f"Pokus {attempt+1}/{max_attempts} selhal u dlaždice {tile}: {e}")
                attempt += 1
                if attempt < max_attempts:
                    time.sleep(1)
        
        logger.error(f"Všechny pokusy o konverzi dlaždice {tile} selhaly po {max_attempts} pokusech.")
        return None

    def process_batch(self, batch: List[str]) -> List[str]:
        """Zpracuje dávku dlaždic paralelně a vrátí seznam úspěšně zpracovaných dlaždic"""
        successful_tiles = []
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_tile = {executor.submit(self.convert_tile, tile): tile for tile in batch}
            
            for future in as_completed(future_to_tile):
                if not self.is_running:
                    executor.shutdown(wait=False, cancel_futures=True)
                    return successful_tiles
                
                tile = future_to_tile[future]
                try:
                    result = future.result(timeout=self.TILE_CONVERSION_TIMEOUT)
                    success = result is not None
                    
                    # Aktualizace stavu
                    status_info = self.status.update(success)
                    
                    # Formátování odhadovaného času dokončení
                    eta_str = ""
                    if status_info["estimated_completion"]:
                        eta_str = status_info["estimated_completion"].strftime("%H:%M:%S")
                    
                    # Pravidelné uvolňování paměti po každých 10 dlaždicích
                    if status_info['processed'] % 10 == 0:
                        self.cleanup_memory()
                    
                    # Vytvoření informační zprávy
                    msg = (f"Zpracováno {status_info['processed']}/{status_info['total']} dlaždic "
                           f"({status_info['percent']:.1f}%), "
                           f"úspěšných: {status_info['successful']}, "
                           f"neúspěšných: {status_info['failed']}, "
                           f"rychlost: {status_info['processing_speed']:.2f} dlaždic/s, "
                           f"odhadovaný čas dokončení: {eta_str}")
                    
                    # Emitování signálů pro aktualizaci GUI
                    self.status_message.emit(msg)
                    self.progress_updated.emit(
                        status_info['processed'], 
                        status_info['total'] * 2,  # *2 protože máme ještě druhou fázi (tvorba VRT)
                        status_info
                    )
                    
                    if success:
                        successful_tiles.append(result)
                    
                except TimeoutError:
                    logger.error(f"Konverze dlaždice {tile} vypršela (timeout).")
                    self.status.update(False)
                except Exception as ex:
                    logger.error(f"Chyba u dlaždice {tile}: {ex}")
                    self.status.update(False)
        
        return successful_tiles

    def run(self):
        try:
            logger.info(f"Spouštím zpracování {len(self.tiles)} dlaždic")
            self.status_message.emit(f"Zahajuji zpracování {len(self.tiles)} dlaždic...")
            
            reprojected_tiles = []
            
            # Rozdělení dlaždic do dávek pro lepší správu paměti
            for i in range(0, len(self.tiles), self.batch_size):
                if not self.is_running:
                    logger.info("Zpracování zastaveno uživatelem")
                    self.status_message.emit("Zpracování zastaveno uživatelem.")
                    return
                
                batch = self.tiles[i:i+self.batch_size]
                logger.info(f"Zpracovávám dávku {i//self.batch_size + 1}/{(len(self.tiles)-1)//self.batch_size + 1} ({len(batch)} dlaždic)")
                self.status_message.emit(f"Zpracovávám dávku {i//self.batch_size + 1}/{(len(self.tiles)-1)//self.batch_size + 1} ({len(batch)} dlaždic)")
                
                # Zpracování dávky
                successful_batch = self.process_batch(batch)
                reprojected_tiles.extend(successful_batch)
                
                # Uvolnění paměti po zpracování dávky
                self.cleanup_memory()
            
            if not self.is_running:
                logger.info("Zpracování zastaveno uživatelem")
                self.status_message.emit("Zpracování zastaveno uživatelem.")
                return
            
            if len(reprojected_tiles) == 0:
                raise Exception("Žádná dlaždice nebyla úspěšně převedena a reprojektována.")
            
            # Vytvoření VRT
            logger.info(f"Zahajuji tvorbu VRT z {len(reprojected_tiles)} úspěšně zpracovaných dlaždic")
            self.status_message.emit(f"Zahajuji tvorbu VRT z {len(reprojected_tiles)} úspěšně zpracovaných dlaždic...")
            
            # Seznam pro vytvoření VRT
            tiles_list_file = os.path.join(os.path.dirname(self.output_file), "tiles_list.txt")
            with open(tiles_list_file, "w", encoding="utf-8") as f:
                for tile in reprojected_tiles:
                    f.write(f"{tile}\n")
            
            # Příprava příkazu pro gdalbuildvrt
            cmd_vrt = ["gdalbuildvrt"]
            rez = self.options.get("resolution")
            if rez == "highest":
                cmd_vrt.extend(["-resolution", "highest"])
            elif rez == "lowest":
                cmd_vrt.extend(["-resolution", "lowest"])
            cmd_vrt.extend([self.output_file, "--optfile", tiles_list_file])
            
            logger.info(f"Spouštím tvorbu VRT pomocí: {' '.join(cmd_vrt)}")
            self.status_message.emit("Vytvářím VRT vrstvu...")
            self.progress_updated.emit(len(self.tiles) + 1, len(self.tiles) * 2, {})
            
            # Pro vytvoření VRT používáme externí volání
            vrt_result = os.system(" ".join(cmd_vrt))
            if vrt_result != 0:
                raise Exception(f"Vytvoření VRT selhalo s kódem {vrt_result}")
            
            self.progress_updated.emit(len(self.tiles) * 2 - 10, len(self.tiles) * 2, {})
            os.remove(tiles_list_file)
            
            # Odstraníme extra kanál v případě potřeby (finální VRT)
            fixed_vrt = os.path.splitext(self.output_file)[0] + "_fixed.vrt"
            cmd_fix = ["gdal_translate", "-of", "VRT", "-b", "1", "-b", "2", "-b", "3", "-b", "4", self.output_file, fixed_vrt]
            logger.info(f"Odstraňuji extra kanál pomocí: {' '.join(cmd_fix)}")
            self.status_message.emit("Optimalizuji VRT vrstvu...")
            
            fix_result = os.system(" ".join(cmd_fix))
            if fix_result == 0:
                os.replace(fixed_vrt, self.output_file)
            else:
                logger.warning(f"Optimalizace VRT selhala s kódem {fix_result}, pokračuji s původním VRT")
            
            self.progress_updated.emit(len(self.tiles) * 2 - 5, len(self.tiles) * 2, {})
            
            # Volitelně vytvoříme JPEG náhled
            if self.options.get("create_jpg", True):
                jpg_output = os.path.splitext(self.output_file)[0] + ".jpg"
                cmd_jpg = ["gdal_translate", "-of", "JPEG", "-co", "PHOTOMETRIC=RGB", "-outsize", "10000", "10000", self.output_file, jpg_output]
                logger.info(f"Vytvářím JPEG s rozměry 10000x10000 pomocí: {' '.join(cmd_jpg)}")
                self.status_message.emit("Vytvářím JPEG náhled...")
                
                try:
                    jpg_result = os.system(" '.join(cmd_jpg)")
                    if jpg_result == 0:
                        logger.info(f"JPEG vytvořen: {jpg_output}")
                    else:
                        logger.warning(f"Vytvoření JPEG selhalo s kódem {jpg_result}")
                except Exception as e:
                    logger.error(f"Chyba při vytváření JPEG: {e}")
            
            self.progress_updated.emit(len(self.tiles) * 2, len(self.tiles) * 2, {})
            
            # Dokončení
            elapsed_time = time.time() - self.status.start_time
            logger.info(f"VRT vytvořeno: {self.output_file} (čas zpracování: {timedelta(seconds=int(elapsed_time))})")
            self.status_message.emit(f"VRT vytvořeno: {self.output_file} (čas zpracování: {timedelta(seconds=int(elapsed_time))})")
            self.vrt_created.emit(self.output_file)
            
            # Finální uvolnění paměti
            self.cleanup_memory()
            
        except Exception as e:
            logger.error(f"Chyba při vytváření VRT: {e}", exc_info=True)
            self.creation_error.emit(str(e))
            # Uvolnění paměti i v případě chyby
            self.cleanup_memory()
