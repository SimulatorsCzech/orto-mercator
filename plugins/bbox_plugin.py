import os
import shapefile
import unicodedata
import re
from shapely.geometry import Polygon, box
from shapely.affinity import scale

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QMessageBox, QSlider, QHBoxLayout, QSpinBox
from PySide6.QtCore import Qt, QTimer, QCoreApplication
from plugins.plugin_base import PluginBase
from plugins.global_context import global_context
from plugins.signal_manager import signal_manager

def sanitize_filename(name: str) -> str:
    """
    Odstraní diakritiku, interpunkci, speciální znaky a mezery z řetězce.
    Použije se k sanitizaci názvů souborů i adresářů tak, aby obsahovaly 
    pouze alfanumerické znaky, podtržítka, pomlčky a tečky.
    """
    normalized = unicodedata.normalize('NFKD', name).encode('ASCII', 'ignore').decode('ASCII')
    sanitized = re.sub(r'[^A-Za-z0-9_.-]', '', normalized)
    return sanitized

class BboxPlugin(PluginBase):
    """
    Plugin načítá polygon ze shapefile příslušného regionu a počítá čtyři varianty bounding boxů:
      1. bbox_rotated_100 – Rotovaný obal (minimálně natočený obdélník) z polygonu s bufferem 50 m.
      2. bbox_rotated_extended – Rotovaný obal z (1) dále zvětšený o nastavitelnou hodnotu (výchozí 50%).
      3. bbox_aligned_100 – Axis-aligned obálka původního polygonu s rozšířením o 50 m na každou stranu.
      4. bbox_aligned_extended – Axis-aligned obálka z (3) dále zvětšená o stejnou hodnotu jako (2).
      
    Výsledky jsou uloženy do global_context:
       "bbox_rotated_100", "bbox_rotated_extended", "bbox_aligned_100", "bbox_aligned_extended"
       "extension_percent" - aktuální hodnota extenze v procentech
    """

    def __init__(self):
        """
        Inicializace pluginu s výchozími hodnotami.
        """
        # Konfigurace pro cestu k shapefile
        self.config = {"shapefile_dir": os.path.join("data", "shapefile")}
        
        # Proměnné pro uložení vypočtených bounding boxů
        self.bbox_rotated_100 = None        # Rotovaný bbox s +50m bufferem
        self.bbox_rotated_extended = None     # Rotovaný bbox s extenzí
        self.bbox_aligned_100 = None          # Zarovnaný bbox s +50m bufferem
        self.bbox_aligned_extended = None     # Zarovnaný bbox s extenzí
        
        # UI komponenty
        self.results_label = None             # Label pro zobrazení výsledků
        self.region_label = None              # Label pro zobrazení aktuálního regionu
        
        # Hodnota extenze v procentech (výchozí 50%)
        self.extension_percent = 50
        
        # UI komponenty pro nastavení extenze
        self.extension_slider = None          # Slider pro nastavení extenze
        self.extension_spinbox = None         # SpinBox pro přesné nastavení extenze

    def name(self) -> str:
        """
        Vrací název pluginu, který se zobrazí v záložce.
        """
        return "Výpočet bounding box"

    def description(self) -> str:
        """
        Vrací popis pluginu, který se může zobrazit v nápovědě nebo tooltipu.
        """
        return ("Plugin vypočítá čtyři varianty bounding boxu načteného z polygonu (ze shapefile): "
                "rotovaný a axis-aligned, každá s 50m rozšířením a dále s nastavitelnou extenzí. "
                "Výsledky se uloží do global_context pod příslušnými klíči.")

    def get_default_config(self) -> dict:
        """
        Vrací výchozí konfiguraci pluginu.
        """
        return self.config

    def update_config(self, new_config: dict):
        """
        Aktualizuje konfiguraci pluginu.
        """
        self.config.update(new_config)

    def calculate_bboxes_from_shapefile(self, region_name: str):
        """
        Načte shapefile a vytvoří Shapely Polygon.
        Poté:
          - bbox_rotated_100: nejprve buffer(50) a následně minimum_rotated_rectangle.
          - bbox_rotated_extended: bbox_rotated_100 zvětšený o extension_percent % (scale factor).
          - bbox_aligned_100: axis-aligned obálka s přičtením 50 m na každou stranu.
          - bbox_aligned_extended: bbox_aligned_100 dále zvětšená o extension_percent %.
        Všechny výsledky se převedou na seznam souřadnic (kde se první bod opakuje na konci)
        a uloží se do global_context.
        """
        # Vymažeme staré hodnoty, aby změna regionu byla patrná
        self.bbox_rotated_100 = None
        self.bbox_rotated_extended = None
        self.bbox_aligned_100 = None
        self.bbox_aligned_extended = None

        # Sanitizace názvu regionu, aby se odstranily nepovolené znaky v názvu souboru.
        sanitized_region = sanitize_filename(region_name)
        shapefile_dir = self.config.get("shapefile_dir")
        shp_path = os.path.join(shapefile_dir, f"{sanitized_region}.shp")
        
        # Kontrola existence souboru
        if not os.path.exists(shp_path):
            QMessageBox.warning(None, "Chyba", f"Shapefile {shp_path} nebyl nalezen.")
            return

        try:
            # Načtení shapefile a vytvoření Shapely polygonu
            r = shapefile.Reader(shp_path)
            shape_rec = r.shape(0)
            points = shape_rec.points
            
            # Kontrola, zda shapefile obsahuje body
            if not points:
                QMessageBox.critical(None, "Chyba", "Shapefile neobsahuje body.")
                return
                
            # Vytvoření Shapely polygonu z bodů
            poly = Polygon(points)
        except Exception as e:
            QMessageBox.critical(None, "Chyba", f"Chyba při čtení shapefile: {e}")
            return

        # Varianta 1: Rotovaný bbox s +50 m buffer.
        rotated_box_100 = poly.buffer(50).minimum_rotated_rectangle
        self.bbox_rotated_100 = list(rotated_box_100.exterior.coords)

        # Varianta 2: Rotovaný extended = scale o (1 + extension_percent/100).
        scale_factor = 1 + (self.extension_percent / 100)
        rotated_box_ext = scale(rotated_box_100, xfact=scale_factor, yfact=scale_factor, origin='centroid')
        self.bbox_rotated_extended = list(rotated_box_ext.exterior.coords)

        # Varianta 3: Axis-aligned bbox – získání obálky polygonu a přidání 50 m margin.
        minx, miny, maxx, maxy = poly.bounds
        self.bbox_aligned_100 = [(minx - 50, miny - 50), (maxx + 50, miny - 50),
                                 (maxx + 50, maxy + 50), (minx - 50, maxy + 50), (minx - 50, miny - 50)]

        # Varianta 4: Axis-aligned extended – zvětšení axis-aligned obálky o extension_percent %.
        aligned_poly_100 = Polygon(self.bbox_aligned_100)
        aligned_poly_ext = scale(aligned_poly_100, xfact=scale_factor, yfact=scale_factor, origin='centroid')
        self.bbox_aligned_extended = list(aligned_poly_ext.exterior.coords)

        # Uložení výsledků do global_context
        global_context["bbox_rotated_100"] = self.bbox_rotated_100
        global_context["bbox_rotated_extended"] = self.bbox_rotated_extended
        global_context["bbox_aligned_100"] = self.bbox_aligned_100
        global_context["bbox_aligned_extended"] = self.bbox_aligned_extended
        global_context["extension_percent"] = self.extension_percent

    def update_results_ui(self):
        """
        Aktualizuje textové zobrazení výsledků – vypíše souřadnice všech čtyř variant.
        Pro přehlednost zobrazuje jen první 4 body každého bounding boxu.
        """
        text = ""
        if self.bbox_rotated_100:
            text += "Rotated bbox-100:\n"
            for pt in self.bbox_rotated_100[:4]:
                text += f"({pt[0]:.2f}, {pt[1]:.2f}) "
            text += "\n"
        else:
            text += "Rotated bbox-100: N/A\n"
            
        if self.bbox_rotated_extended:
            text += f"\nRotated extended bbox (+{self.extension_percent}%):\n"
            for pt in self.bbox_rotated_extended[:4]:
                text += f"({pt[0]:.2f}, {pt[1]:.2f}) "
            text += "\n"
        else:
            text += "Rotated extended bbox: N/A\n"

        if self.bbox_aligned_100:
            text += "\nAxis-aligned bbox-100:\n"
            for pt in self.bbox_aligned_100[:4]:
                text += f"({pt[0]:.2f}, {pt[1]:.2f}) "
            text += "\n"
        else:
            text += "Axis-aligned bbox-100: N/A\n"
            
        if self.bbox_aligned_extended:
            text += f"\nAxis-aligned extended bbox (+{self.extension_percent}%):\n"
            for pt in self.bbox_aligned_extended[:4]:
                text += f"({pt[0]:.2f}, {pt[1]:.2f}) "
        else:
            text += "Axis-aligned extended bbox: N/A"
            
        if self.results_label is not None:
            self.results_label.setText(text)

    def on_extension_changed(self, value):
        """
        Slot volaný při změně hodnoty extenze (ze slideru či spinboxu).
        Aktualizuje hodnotu extenze a přepočítá bounding boxy.
        """
        self.extension_percent = value
        
        if self.extension_slider.value() != value:
            self.extension_slider.setValue(value)
        if self.extension_spinbox.value() != value:
            self.extension_spinbox.setValue(value)
        
        # Aktualizujeme globální region, pokud je již nastaven
        current_region = global_context.get("selected_region")
        if current_region:
            self.calculate_bboxes_from_shapefile(current_region)
            self.update_results_ui()
            signal_manager.extension_changed.emit(value)
            # Emitujeme signál, aby další pluginy (např. MapPlugin) věděly, že se změnil global_context
            signal_manager.global_context_updated.emit(global_context)

    def on_region_changed(self, region_name):
        """
        Slot volaný při změně vybraného regionu.
        Aktualizuje globální kontext, přepočítá bounding boxy a potom aktualizuje UI.
        """
        if not region_name:
            return
        # Aktualizace zobrazení regionu v UI
        self.region_label.setText(f"Vybraný region: {region_name}")
        # Prostřednictvím processEvents zajistíme, že se UI aktualizuje
        QCoreApplication.processEvents()
        # Nastavení aktuálního regionu do global_context
        global_context["selected_region"] = region_name
        # Přepočet bounding boxů s aktuálním regionem a aktualizace UI
        self.calculate_bboxes_from_shapefile(region_name)
        self.update_results_ui()
        # Emitujeme signál, aby další pluginy (např. MapPlugin) věděly, že se změnil global_context
        signal_manager.global_context_updated.emit(global_context)


    def setup_ui(self, parent) -> QWidget:
        """
        Vytvoří uživatelské rozhraní pluginu.
        Obsahuje:
          - Informační labely
          - Slider a SpinBox pro nastavení hodnoty extenze
          - Label pro zobrazení výsledků
        """
        widget = QWidget(parent)
        layout = QVBoxLayout(widget)
        
        title = QLabel("<h2>Výpočet bounding box</h2>", widget)
        layout.addWidget(title)
        
        info = QLabel("Plugin reaguje na změnu regionu a uloží do global_context čtyři varianty obalů:\n"
                      " - bbox_rotated_100\n - bbox_rotated_extended\n"
                      " - bbox_aligned_100\n - bbox_aligned_extended", widget)
        layout.addWidget(info)
        
        self.region_label = QLabel("Vybraný region: N/A", widget)
        layout.addWidget(self.region_label)
        
        extension_layout = QHBoxLayout()
        extension_label = QLabel("Hodnota extenze (%):", widget)
        extension_layout.addWidget(extension_label)
        
        self.extension_slider = QSlider(Qt.Horizontal, widget)
        self.extension_slider.setMinimum(0)
        self.extension_slider.setMaximum(200)
        self.extension_slider.setValue(self.extension_percent)
        self.extension_slider.setTickPosition(QSlider.TicksBelow)
        self.extension_slider.setTickInterval(25)
        extension_layout.addWidget(self.extension_slider)
        
        self.extension_spinbox = QSpinBox(widget)
        self.extension_spinbox.setMinimum(0)
        self.extension_spinbox.setMaximum(200)
        self.extension_spinbox.setValue(self.extension_percent)
        self.extension_spinbox.setSuffix("%")
        extension_layout.addWidget(self.extension_spinbox)
        
        layout.addLayout(extension_layout)
        
        self.extension_slider.valueChanged.connect(self.on_extension_changed)
        self.extension_spinbox.valueChanged.connect(self.on_extension_changed)
        
        self.results_label = QLabel("Výsledky: N/A", widget)
        layout.addWidget(self.results_label)
        
        signal_manager.region_changed.connect(self.on_region_changed)
        current_region = global_context.get("selected_region")
        if current_region:
            self.on_region_changed(current_region)
        
        return widget

    def execute(self, data):
        pass
# KONEC SOUBORU
