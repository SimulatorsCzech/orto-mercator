
"""
Plugin: Načtení INSPIRE územních celků a stažení bbox v EPSG:5514 (nyní ukládá shapefile do WebMercator)

Tento plugin načte územní správní jednotky ze souboru INSPIRE XML, seskupí je podle národní úrovně
(nationalLevelName) a nabídne uživatelsky přehledný výběr v stromovém widgetu. Dále umožňuje:
 – Automatické vytvoření shapefile pro vybraný region (nebo hromadně pro všechny regiony, pokud si uživatel to přeje).
 – Umožňuje také nahrát vlastní shapefile, které musí být v EPSG:5514.
 – Navíc lze vytvořit shapefile pro 1°x1° geografický čtverec zadaný uživatelem (např. "N50E015"), kdy
   se vstupní hodnota interpretuje jako levý dolní roh; k tomuto čtverci se následně přidá okraj o 0,2°.
Výsledný shapefile se transformuje do WebMercator (EPSG:3857).

Autor: [Vaše jméno]
Verze: 1.1
"""

import os
import time
import xml.etree.ElementTree as ET
import shapefile
import re
import unicodedata

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QMessageBox, QTreeWidget, QTreeWidgetItem,
    QPushButton, QProgressBar, QHBoxLayout, QFileDialog, QLineEdit, QInputDialog
)
from PySide6.QtCore import QThread, Signal, Qt

from pyproj import Transformer

from plugins.plugin_base import PluginBase
from plugins.global_context import global_context
from plugins.signal_manager import signal_manager

# Funkce pro sanitizaci názvů souborů - odstraní diakritiku a nepovolené znaky
def sanitize_filename(name: str) -> str:
    normalized = unicodedata.normalize('NFKD', name).encode('ASCII', 'ignore').decode('ASCII')
    sanitized = re.sub(r'[^A-Za-z0-9_.-]', '', normalized)
    return sanitized

# ---------------------------------------------------------------------------
# Worker pro hromadné vytváření shapefile (pro všechny regiony, u kterých shapefile ještě neexistuje)
# ---------------------------------------------------------------------------
class ShapefileCreatorWorker(QThread):
    progress_updated = Signal(int, int, float)  # počet zpracovaných regionů, celkový počet, odhad zbývajícího času (v sekundách)
    creation_finished = Signal()
    creation_error = Signal(str)

    def __init__(self, region_data: dict, output_dir: str, save_func):
        """
        :param region_data: Slovník region_name -> {'points': list bodů, 'national_level': hodnota nebo None}
        :param output_dir: Cesta, kam se shapefile ukládají
        :param save_func: Funkce pro uložení shapefile, očekává argumenty (region_name, body)
        """
        super().__init__()
        self.region_data = region_data
        self.output_dir = output_dir
        self.save_func = save_func
        self._is_running = True

    def stop(self):
        self._is_running = False

    def run(self):
        total = len(self.region_data)
        completed = 0
        start_time = time.time()
        for region_name, info in sorted(self.region_data.items()):
            if not self._is_running:
                break
            clean_name = sanitize_filename(region_name)
            shapefile_path = os.path.join(self.output_dir, f"{clean_name}.shp")
            # Pokud shapefile již existuje, považujeme jej za zpracovaný
            if os.path.exists(shapefile_path):
                completed += 1
                elapsed = time.time() - start_time
                remaining = (elapsed / completed) * (total - completed) if completed else 0
                self.progress_updated.emit(completed, total, remaining)
                continue
            try:
                self.save_func(region_name, info['points'])
                completed += 1
            except Exception as e:
                self.creation_error.emit(f"Chyba u regionu {region_name}: {e}")
            elapsed = time.time() - start_time
            remaining = (elapsed / completed) * (total - completed) if completed else 0
            self.progress_updated.emit(completed, total, remaining)
        self.creation_finished.emit()

# ---------------------------------------------------------------------------
# Hlavní plugin pro načtení INSPIRE územních celků
# ---------------------------------------------------------------------------
class UzemniCelkyInspirePlugin(PluginBase):
    def __init__(self):
        self.config = {
            "xml_path": os.path.join("data", "uzemni_celky_cr.xml"),
            "shapefile_dir": os.path.join("data", "shapefile")
        }
        # region_data bude slovník: { region_name : { 'points': [(x,y), ...], 'national_level': hodnota } }
        self.region_data = {}
        self.tree = None    # QTreeWidget pro výběr regionů
        self.status_label = None
        self.search_box = None  # Pro filtraci regionů
        self.bbox_box = None    # Pro zadání vstupu jako "N50E015"
        self.create_all_button = None
        self.stop_all_button = None
        self.progress_bar = None
        self.progress_info_label = None
        self.download_bbox_button = None

        # Worker pro hromadné vytváření shapefile
        self.creator_worker = None

        # Cesta k vlastnímu shapefile, pokud uživatel nahraje
        self.user_shapefile = None

    def name(self) -> str:
        return "Načtení INSPIRE územních celků"

    def description(self) -> str:
        return ("Plugin načte územní správní jednotky z INSPIRE XML souboru, seskupí je podle národní úrovně "
                "a umožní uživateli výběr regionu. Rovněž automaticky vytvoří shapefile pro vybraný region, "
                "umožňuje hromadné vytváření shapefile, nahrání vlastního shapefile a také vytvoření shapefile "
                "pro 1°x1° čtverec (s okrajem o 0,2°). Shapefile se transformují do WebMercator (EPSG:3857).")

    def get_default_config(self) -> dict:
        return self.config

    def update_config(self, new_config: dict):
        self.config.update(new_config)

    def sanitize_filename(self, name: str) -> str:
        return sanitize_filename(name)

    def parse_xml(self):
        """
        Parsuje INSPIRE XML soubor a naplní self.region_data.
        Extrahuje se název regionu, případně národní úroveň a souřadnicový řetězec (posList).
        Předpokládá se, že souřadnice v XML jsou v EPSG:5514.
        """
        xml_path = self.config.get("xml_path")
        if not os.path.exists(xml_path):
            raise FileNotFoundError(f"Soubor {xml_path} nebyl nalezen.")
        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()
        except ET.ParseError as e:
            raise Exception(f"Chyba při parsování XML: {e}")
        self.region_data.clear()

        # Pomocná funkce pro získání lokálního názvu tagu
        def local_name(tag):
            return tag.split("}", 1)[1] if "}" in tag else tag

        # Projdeme všechny elementy v XML a hledáme regionové členy
        for member in root.findall(".//"):
            if local_name(member.tag) != "member":
                continue
            for child in member:
                if local_name(child.tag).endswith("AdministrativeUnit"):
                    admin_unit = child
                    region_primary = None
                    for elem in admin_unit.iter():
                        if local_name(elem.tag) == "SpellingOfName":
                            for sub in elem:
                                if local_name(sub.tag) == "text" and sub.text:
                                    region_primary = sub.text.strip()
                                    break
                            if region_primary:
                                break
                    if not region_primary:
                        continue
                    # Získání hodnoty národní úrovně
                    national_level = None
                    for elem in admin_unit.iter():
                        if local_name(elem.tag) == "nationalLevelName":
                            for sub in elem.iter():
                                if local_name(sub.tag) == "LocalisedCharacterString" and sub.text:
                                    national_level = sub.text.strip()
                                    break
                            if national_level:
                                break
                    # Sestavení regionového názvu
                    region_name = f"{region_primary}-{national_level}" if national_level else region_primary
                    # Unikátní kód (volitelný)
                    unique_code = None
                    for elem in admin_unit.iter():
                        if local_name(elem.tag) == "SHNCode":
                            for sub in elem.iter():
                                if local_name(sub.tag) == "identifier" and sub.text:
                                    unique_code = sub.text.strip()
                                    break
                            if unique_code:
                                break
                    if unique_code and region_name in self.region_data:
                        region_name = f"{region_name}-{unique_code}"
                    # Načítání souřadnic (posList)
                    poslist = None
                    for elem in admin_unit.iter():
                        if local_name(elem.tag) == "posList" and elem.text:
                            poslist = elem.text.strip()
                            break
                    if not poslist:
                        continue
                    try:
                        coords = [float(v) for v in poslist.split()]
                        if len(coords) % 2 != 0:
                            continue
                        points = [(coords[i], coords[i+1]) for i in range(0, len(coords), 2)]
                    except ValueError:
                        continue
                    self.region_data[region_name] = {'points': points, 'national_level': national_level}
                    break

    def save_shapefile(self, region_name: str, points: list) -> bool:
        """
        Uloží body (polygon) jako shapefile.
        Nejprve transformuje body z EPSG:5514 (zdrojové, jak je v XML) do WebMercator (EPSG:3857).
        Pokud shapefile již existuje, nebude přepsán.
        Vytvoří i .prj soubor s definicí EPSG:3857.
        """
        output_dir = self.config.get("shapefile_dir")
        os.makedirs(output_dir, exist_ok=True)
        clean_name = sanitize_filename(region_name)
        shapefile_path = os.path.join(output_dir, f"{clean_name}.shp")
        if os.path.exists(shapefile_path):
            return True
        try:
            # Transformace z EPSG:5514 do WebMercator (EPSG:3857)
            transformer = Transformer.from_crs("EPSG:5514", "EPSG:3857", always_xy=True)
            transformed_points = [transformer.transform(x, y) for (x, y) in points]
            writer = shapefile.Writer(shapefile_path, shapeType=shapefile.POLYGON)
            writer.autoBalance = 1
            writer.field("NAME", "C")
            writer.poly([transformed_points])
            writer.record(region_name)
            writer.close()
            # Aktualizovaná definice projekce pro WebMercator (EPSG:3857)
            prj_path = os.path.splitext(shapefile_path)[0] + ".prj"
            prj_text = (
                'PROJCS["WGS 84 / Pseudo-Mercator",'
                'GEOGCS["WGS 84",'
                'DATUM["WGS_1984",'
                'SPHEROID["WGS 84",6378137,298.257223563,AUTHORITY["EPSG","7030"]],'
                'AUTHORITY["EPSG","6326"]],'
                'PRIMEM["Greenwich",0],'
                'UNIT["degree",0.0174532925199433,AUTHORITY["EPSG","9122"]],'
                'AUTHORITY["EPSG","4326"]],'
                'PROJECTION["Mercator_1SP"],'
                'PARAMETER["central_meridian",0],'
                'PARAMETER["scale_factor",1],'
                'PARAMETER["false_easting",0],'
                'PARAMETER["false_northing",0],'
                'UNIT["metre",1,AUTHORITY["EPSG","9001"]],'
                'AUTHORITY["EPSG","3857"]]'
            )
            with open(prj_path, "w") as prj_file:
                prj_file.write(prj_text)
            return True
        except Exception as e:
            if self.status_label:
                self.status_label.setText(f"Chyba při ukládání shapefile: {e}")
            return False

    def download_bbox_shapefile(self, bbox_str: str):
        """
        Vytváří shapefile na základě zadaného textu (např. "N50E015").
        Text je interpretován jako levý dolní roh 1°x1° čtverce a k němu se přidá okraj o 0,2°.
        Polygon se vytvoří v EPSG:4326 a poté transformuje do WebMercator (EPSG:3857)
        před uložením jako shapefile.
        """
        pattern = r'^([NS])(\d{2})([EW])(\d{3})$'
        m = re.match(pattern, bbox_str.strip().upper())
        if not m:
            QMessageBox.critical(None, "Chyba", "Vstup nemá správný formát. Například zadejte 'N50E015'.")
            return
        lat_sign = 1 if m.group(1) == 'N' else -1
        lat = lat_sign * float(m.group(2))
        lon_sign = 1 if m.group(3) == 'E' else -1
        lon = lon_sign * float(m.group(4))
        min_lon = lon - 0.2
        min_lat = lat - 0.2
        max_lon = lon + 1.2
        max_lat = lat + 1.2
        polygon_geog = [
            (min_lon, min_lat),
            (max_lon, min_lat),
            (max_lon, max_lat),
            (min_lon, max_lat),
            (min_lon, min_lat)
        ]
        # Transformace přímo z EPSG:4326 do WebMercator (EPSG:3857)
        transformer = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
        polygon_proj = [transformer.transform(x, y) for (x, y) in polygon_geog]
        
        region_name = f"BBox_{bbox_str.strip().upper()}"
        output_dir = self.config.get("shapefile_dir")
        os.makedirs(output_dir, exist_ok=True)
        clean_name = sanitize_filename(region_name)
        shapefile_path = os.path.join(output_dir, f"{clean_name}.shp")
        
        try:
            # Ukládáme přímo WebMercator souřadnice, bez další transformace
            writer = shapefile.Writer(shapefile_path, shapeType=shapefile.POLYGON)
            writer.autoBalance = 1
            writer.field("NAME", "C")
            writer.poly([polygon_proj])
            writer.record(region_name)
            writer.close()
            
            # Definice projekce pro WebMercator (EPSG:3857)
            prj_path = os.path.splitext(shapefile_path)[0] + ".prj"
            prj_text = (
                'PROJCS["WGS 84 / Pseudo-Mercator",'
                'GEOGCS["WGS 84",'
                'DATUM["WGS_1984",'
                'SPHEROID["WGS 84",6378137,298.257223563,AUTHORITY["EPSG","7030"]],'
                'AUTHORITY["EPSG","6326"]],'
                'PRIMEM["Greenwich",0],'
                'UNIT["degree",0.0174532925199433,AUTHORITY["EPSG","9122"]],'
                'AUTHORITY["EPSG","4326"]],'
                'PROJECTION["Mercator_1SP"],'
                'PARAMETER["central_meridian",0],'
                'PARAMETER["scale_factor",1],'
                'PARAMETER["false_easting",0],'
                'PARAMETER["false_northing",0],'
                'UNIT["metre",1,AUTHORITY["EPSG","9001"]],'
                'AUTHORITY["EPSG","3857"]]'
            )
            with open(prj_path, "w") as prj_file:
                prj_file.write(prj_text)
                
            # Aktualizace globálního kontextu
            global_context["selected_region"] = region_name
            global_context["selected_shapefile"] = shapefile_path
            signal_manager.region_changed.emit(region_name)
            
            QMessageBox.information(None, "Úspěch", f"Shapefile pro bbox {bbox_str} byl úspěšně vytvořen.")
        except Exception as e:
            QMessageBox.critical(None, "Chyba", f"Při vytváření shapefile pro bbox {bbox_str} došlo k chybě: {str(e)}")

    def filter_tree(self, text: str):
        """
        Prochází položky v QTreeWidgetu a skryje ty, které neobsahují hledaný řetězec (bez ohledu na velikost písmen).
        """
        text = text.lower().strip()
        for i in range(self.tree.topLevelItemCount()):
            parent = self.tree.topLevelItem(i)
            parent_visible = False
            for j in range(parent.childCount()):
                child = parent.child(j)
                if text in child.text(0).lower():
                    child.setHidden(False)
                    parent_visible = True
                else:
                    child.setHidden(True)
            parent.setHidden(not parent_visible)

    def load_regions(self):
        """
        Načte regiony z INSPIRE XML a naplní QTreeWidget seskupeným výběrem dle nationalLevelName.
        """
        try:
            self.parse_xml()
            self.tree.clear()
            if self.user_shapefile:
                vlastni_item = QTreeWidgetItem(self.tree)
                vlastni_item.setText(0, f"Vlastní: {os.path.basename(self.user_shapefile)}")
            groups = {}
            for region_name, info in sorted(self.region_data.items()):
                group = info['national_level'] if info['national_level'] is not None else "Nezařazené"
                groups.setdefault(group, []).append(region_name)
            for group, regions in sorted(groups.items()):
                parent_item = QTreeWidgetItem(self.tree)
                parent_item.setText(0, group)
                parent_item.setFlags(parent_item.flags() & ~Qt.ItemIsSelectable)
                for reg in regions:
                    child_item = QTreeWidgetItem(parent_item)
                    child_item.setText(0, reg)
            self.tree.expandAll()
            self.status_label.setText("Regiony byly úspěšně načteny.")
            if self.tree.topLevelItemCount() > 0:
                first_parent = self.tree.topLevelItem(0)
                if first_parent.childCount() > 0:
                    region_name = first_parent.child(0).text(0)
                    global_context["selected_region"] = region_name
                    info = self.region_data.get(region_name)
                    if info and self.save_shapefile(region_name, info['points']):
                        clean_name = sanitize_filename(region_name)
                        shapefile_path = os.path.join(self.config.get("shapefile_dir"), f"{clean_name}.shp")
                        global_context["selected_shapefile"] = shapefile_path
                        signal_manager.region_changed.emit(region_name)
        except Exception as e:
            self.status_label.setText(f"Chyba při načítání regionů: {e}")
            QMessageBox.critical(None, "Chyba", str(e))

    def on_region_changed(self):
        """
        Slot pro změnu výběru v QTreeWidgetu. Uloží vybraný region, automaticky vytvoří shapefile
        a aktualizuje globální kontext.
        """
        selected = self.tree.currentItem()
        if not selected:
            return
        region_name = selected.text(0)
        if selected.parent() is None:
            return  # neumožňujeme volbu nadřazené skupiny
        if region_name.startswith("Vlastní:"):
            global_context["selected_region"] = region_name
            global_context["selected_shapefile"] = self.user_shapefile
            signal_manager.region_changed.emit(region_name)
            self.status_label.setText(f"Používá se vlastní shapefile: {os.path.basename(self.user_shapefile)}")
            return
        info = self.region_data.get(region_name)
        if not info:
            self.status_label.setText(f"Region {region_name} nemá platná data.")
            return
        if self.save_shapefile(region_name, info['points']):
            global_context["selected_region"] = region_name
            clean_name = sanitize_filename(region_name)
            shapefile_path = os.path.join(self.config.get("shapefile_dir"), f"{clean_name}.shp")
            global_context["selected_shapefile"] = shapefile_path
            signal_manager.region_changed.emit(region_name)
            self.status_label.setText(f"Region {region_name} vybrán a shapefile uložen.")
        else:
            self.status_label.setText(f"Chyba při ukládání shapefile pro {region_name}.")

    def on_create_all_clicked(self):
        """
        Spustí hromadné vytváření shapefile pro všechny regiony.
        """
        output_dir = self.config.get("shapefile_dir")
        os.makedirs(output_dir, exist_ok=True)
        if not self.region_data:
            QMessageBox.warning(None, "Chyba", "Nejsou k dispozici regionová data. Načtěte XML.")
            return
        self.creator_worker = ShapefileCreatorWorker(self.region_data, output_dir, self.save_shapefile)
        self.creator_worker.progress_updated.connect(self.on_creation_progress)
        self.creator_worker.creation_finished.connect(self.on_creation_finished)
        self.creator_worker.creation_error.connect(self.on_creation_error)
        self.creator_worker.start()
        self.status_label.setText("Spouštím hromadné vytváření shapefile...")

    def on_stop_creation_clicked(self):
        if self.creator_worker:
            self.creator_worker.stop()
            self.status_label.setText("Hromadné vytváření shapefile bylo zastaveno.")

    def on_creation_progress(self, completed: int, total: int, remaining: float):
        percent = int(completed / total * 100) if total else 0
        self.progress_bar.setValue(percent)
        self.progress_info_label.setText(f"{completed}/{total} regionů dokončeno, zbývá: {total - completed}. Odhad: {int(remaining)} s.")

    def on_creation_finished(self):
        self.status_label.setText("Hromadné vytváření shapefile dokončeno.")
        self.progress_info_label.setText("")
        self.creator_worker = None

    def on_creation_error(self, error_message: str):
        self.status_label.setText(f"Chyba při tvorbě shapefile: {error_message}")

    def on_load_shapefile(self):
        file_path, _ = QFileDialog.getOpenFileName(None, "Vyberte vlastní shapefile", "", "Shapefile (*.shp)")
        if not file_path:
            return
        prj_path = os.path.splitext(file_path)[0] + ".prj"
        if not os.path.exists(prj_path):
            QMessageBox.warning(None, "Upozornění", "Vybraný shapefile nemá soubor .prj; předpokládá se EPSG:5514.")
        else:
            QMessageBox.information(None, "Informace", "Zkontrolujte, zda je shapefile v EPSG:5514.")
        self.user_shapefile = file_path
        # Odstraníme příponu .shp z názvu souboru
        basename = os.path.splitext(os.path.basename(file_path))[0]
        custom_item_text = f"{basename}"
        custom_item = QTreeWidgetItem(self.tree)
        custom_item.setText(0, custom_item_text)
        self.tree.insertTopLevelItem(0, custom_item)
        self.tree.setCurrentItem(custom_item)
        global_context["selected_region"] = custom_item_text
        global_context["selected_shapefile"] = file_path
        signal_manager.region_changed.emit(custom_item_text)
        self.status_label.setText(f"Načten vlastní shapefile: {basename}.")

    def on_download_bbox_clicked(self):
        bbox_text = self.bbox_box.text()
        if not bbox_text:
            QMessageBox.warning(None, "Upozornění", "Zadejte vstup např. 'N50E015'.")
            return
        self.download_bbox_shapefile(bbox_text)

    def setup_ui(self, parent: QWidget) -> QWidget:
        widget = QWidget(parent)
        layout = QVBoxLayout(widget)

        title = QLabel("<h2>Načtení INSPIRE územních celků</h2>", widget)
        layout.addWidget(title)

        info_label = QLabel("Regiony jsou načteny z INSPIRE XML a seskupeny dle národní úrovně.<br>"
                             "Můžete filtrovat pomocí vyhledávacího pole, zadat bbox (např. 'N50E015'), "
                             "nahrát vlastní shapefile a spustit hromadné vytváření shapefile.", widget)
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        self.search_box = QLineEdit(widget)
        self.search_box.setPlaceholderText("Hledat region (např. 'králové')...")
        self.search_box.textChanged.connect(self.filter_tree)
        layout.addWidget(self.search_box)

        self.bbox_box = QLineEdit(widget)
        self.bbox_box.setPlaceholderText("Zadejte bbox (např. 'N50E015')...")
        layout.addWidget(self.bbox_box)

        self.download_bbox_button = QPushButton("Stáhnout bbox", widget)
        self.download_bbox_button.clicked.connect(self.on_download_bbox_clicked)
        layout.addWidget(self.download_bbox_button)

        load_custom_button = QPushButton("Nahrát vlastní shapefile", widget)
        load_custom_button.clicked.connect(self.on_load_shapefile)
        layout.addWidget(load_custom_button)

        self.tree = QTreeWidget(widget)
        self.tree.setHeaderHidden(True)
        self.tree.itemSelectionChanged.connect(self.on_region_changed)
        layout.addWidget(self.tree)

        self.status_label = QLabel("", widget)
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.create_all_button = QPushButton("Vytvořit chybějící shapefile", widget)
        self.create_all_button.clicked.connect(self.on_create_all_clicked)
        layout.addWidget(self.create_all_button)

        self.stop_all_button = QPushButton("Zastavit tvorbu", widget)
        self.stop_all_button.clicked.connect(self.on_stop_creation_clicked)
        layout.addWidget(self.stop_all_button)

        self.progress_bar = QProgressBar(widget)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        self.progress_info_label = QLabel("", widget)
        self.progress_info_label.setWordWrap(True)
        layout.addWidget(self.progress_info_label)

        # Načtení regionů
        self.load_regions()

        return widget

    def execute(self, data):
        pass

# KONEC SOUBORU
