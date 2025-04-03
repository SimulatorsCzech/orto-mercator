
import os
import json
import shapefile
import tempfile
import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QMessageBox, QCheckBox, QHBoxLayout,
    QGroupBox
)
from PySide6.QtWebEngineWidgets import QWebEngineView
try:
    from PySide6.QtWebEngineWidgets import QWebEngineSettings
except ImportError:
    from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtCore import QUrl

from plugins.plugin_base import PluginBase
from plugins.global_context import global_context
from plugins.signal_manager import signal_manager

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

def sanitize_filename(name: str) -> str:
    """
    Odstraňuje diakritiku a nežádoucí znaky z řetězce.
    """
    import unicodedata, re
    normalized = unicodedata.normalize('NFKD', name).encode('ASCII', 'ignore').decode('ASCII')
    return re.sub(r'[^A-Za-z0-9_.-]', '', normalized)

class MapPlugin(PluginBase):
    """
    Plugin pro interaktivní mapu využívající WMS podklad od ČÚZK.
    Zobrazuje čtyři varianty bounding boxů a skutečný tvar oblasti ze shapefile.
    Nyní se předpokládá, že všechna data (shapefile, bboxy) jsou v projekční soustavě WebMercator (EPSG:3857).
    """
    def __init__(self):
        # Inicializace výchozích hodnot pro mapu a stav checkboxů
        self.map_view = None
        self.region_label = None
        self.extension_label = None

        self.show_rotated_100 = True
        self.show_rotated_extended = True
        self.show_aligned_100 = True
        self.show_aligned_extended = True
        self.show_polygon = True
        self.extension_percent = 50

        # Checkboxy se vytvoří během setup_ui
        self.rotated_100_checkbox = None
        self.rotated_extended_checkbox = None
        self.aligned_100_checkbox = None
        self.aligned_extended_checkbox = None
        self.polygon_checkbox = None

    def name(self) -> str:
        return "Interaktivní mapa (WMS)"

    def description(self) -> str:
        return ("Plugin zobrazuje interaktivní mapu s WMS podkladem z ČÚZK, využívá bounding box hodnoty "
                "z global_context a zobrazuje v reálném čase čtyři varianty obalů a skutečný tvar oblasti.")

    def get_default_config(self) -> dict:
        return {"shapefile_dir": os.path.join("data", "shapefile")}

    def update_config(self, new_config: dict):
        # Aktualizace konfigurace – zde se aktuálně jen slučuje se základní konfigurací
        config = self.get_default_config()
        config.update(new_config)

    def build_map_html_content(
        self,
        region_name: str,
        polygon: list,
        bbox_rotated_100: list,
        bbox_rotated_extended: list,
        bbox_aligned_100: list,
        bbox_aligned_extended: list
    ) -> str:
        """
        Sestaví HTML obsah pro zobrazení mapy.
        Všechny geometrie se předpokládají v souřadnicovém systému WebMercator (EPSG:3857).
        """
        # Převedeme data do JSON pro skript
        polygon_js = json.dumps(polygon)
        rotated100_js = json.dumps(bbox_rotated_100)
        rotatedExt_js = json.dumps(bbox_rotated_extended)
        aligned100_js = json.dumps(bbox_aligned_100)
        alignedExt_js = json.dumps(bbox_aligned_extended)

        wms_url = "https://ags.cuzk.gov.cz/arcgis1/services/ZTM/ZTM50/MapServer/WMSServer?"
        html_content = f"""<!DOCTYPE html>
<html>
  <head>
    <meta charset="utf-8">
    <title>Mapa - {region_name}</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.7.1/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.7.1/dist/leaflet.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/proj4js/2.7.5/proj4.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/proj4leaflet/1.0.2/proj4leaflet.js"></script>
    <style>
      #map {{
        width: 100%;
        height: 100vh;
      }}
      .info {{
        position: absolute;
        top: 10px;
        left: 10px;
        z-index: 1000;
        background: white;
        padding: 10px;
        border: 1px solid #ccc;
      }}
    </style>
  </head>
  <body>
    <div id="map"></div>
    <div class="info">
      <h3>Region: {region_name}</h3>
      <p><span style="color: green;">■</span> Rotovaný bbox-100</p>
      <p><span style="color: blue;">■</span> Rotovaný extended bbox (+{self.extension_percent}%)</p>
      <p><span style="color: purple;">■</span> Axis-aligned bbox-100</p>
      <p><span style="color: orange;">■</span> Axis-aligned extended bbox (+{self.extension_percent}%)</p>
      <p><span style="color: red;">■</span> Skutečný tvar</p>
    </div>
    <script>
      var polygonCoords = {polygon_js};
      var rotated100 = {rotated100_js};
      var rotatedExtended = {rotatedExt_js};
      var aligned100 = {aligned100_js};
      var alignedExtended = {alignedExt_js};

      var showRotated100 = {str(self.show_rotated_100).lower()};
      var showRotatedExtended = {str(self.show_rotated_extended).lower()};
      var showAligned100 = {str(self.show_aligned_100).lower()};
      var showAlignedExtended = {str(self.show_aligned_extended).lower()};
      var showPolygon = {str(self.show_polygon).lower()};

      // Využijeme vestavěnou CRS pro WebMercator (EPSG:3857)
      function projectPoints(points) {{
        points = points || [];
        return points.map(function(coord) {{
          return L.CRS.EPSG3857.unproject(new L.Point(coord[0], coord[1]));
        }});
      }}

      var polygonLatLng = projectPoints(polygonCoords);
      var rotated100LatLng = projectPoints(rotated100);
      var rotatedExtendedLatLng = projectPoints(rotatedExtended);
      var aligned100LatLng = projectPoints(aligned100);
      var alignedExtendedLatLng = projectPoints(alignedExtended);

      var center = L.latLng(0, 0);
      if(alignedExtendedLatLng.length > 0) {{
        var sumLat = 0, sumLng = 0;
        alignedExtendedLatLng.forEach(function(pt){{
          sumLat += pt.lat;
          sumLng += pt.lng;
        }});
        center = L.latLng(sumLat/alignedExtendedLatLng.length, sumLng/alignedExtendedLatLng.length);
      }}

      var map = L.map('map').setView(center, 5);
      var wmsLayer = L.tileLayer.wms("{wms_url}", {{
        layers: "0",
        format: "image/png",
        transparent: true,
        version: "1.3.0",
        attribution: "ČÚZK"
      }});
      wmsLayer.addTo(map);

      var layers = [];

      if (showRotated100 && rotated100LatLng.length > 0) {{
        var layer1 = L.polygon(rotated100LatLng, {{
          color: 'green',
          weight: 2,
          fill: false,
          dashArray: '5,5'
        }}).addTo(map);
        layer1.bindPopup("Rotovaný bbox-100");
        layers.push(layer1);
      }}
      if (showRotatedExtended && rotatedExtendedLatLng.length > 0) {{
        var layer2 = L.polygon(rotatedExtendedLatLng, {{
          color: 'blue',
          weight: 2,
          fill: false,
          dashArray: '5,5'
        }}).addTo(map);
        layer2.bindPopup("Rotovaný extended bbox (+" + {self.extension_percent} + "%)");
        layers.push(layer2);
      }}
      if (showAligned100 && aligned100LatLng.length > 0) {{
        var layer3 = L.polygon(aligned100LatLng, {{
          color: 'purple',
          weight: 2,
          fill: false,
          dashArray: '5,5'
        }}).addTo(map);
        layer3.bindPopup("Axis-aligned bbox-100");
        layers.push(layer3);
      }}
      if (showAlignedExtended && alignedExtendedLatLng.length > 0) {{
        var layer4 = L.polygon(alignedExtendedLatLng, {{
          color: 'orange',
          weight: 2,
          fill: false,
          dashArray: '5,5'
        }}).addTo(map);
        layer4.bindPopup("Axis-aligned extended bbox (+" + {self.extension_percent} + "%)");
        layers.push(layer4);
      }}
      if (showPolygon && polygonLatLng.length > 0) {{
        var layer5 = L.polygon(polygonLatLng, {{
          color: 'red',
          weight: 3,
          fillOpacity: 0.3
        }}).addTo(map);
        layer5.bindPopup("Skutečný tvar oblasti");
        layers.push(layer5);
      }}
      if(layers.length > 0) {{
        var group = new L.featureGroup(layers);
        map.fitBounds(group.getBounds());
      }}
    </script>
  </body>
</html>
"""
        return html_content

    def generate_map_html_file(self, html_content: str) -> str:
        """
        Uloží HTML obsah do dočasného souboru a vrátí jeho cestu.
        """
        temp_html = tempfile.NamedTemporaryFile(delete=False, suffix=".html", mode="w", encoding="utf-8")
        temp_html.write(html_content)
        temp_html.close()
        return temp_html.name

    def on_extension_changed(self, value: int):
        self.extension_percent = value
        if self.extension_label:
            self.extension_label.setText(f"Hodnota extenze: {value}%")
        current_region = global_context.get("selected_region")
        if current_region:
            self.on_region_changed(current_region)

    def on_checkbox_changed(self):
        self.show_rotated_100 = self.rotated_100_checkbox.isChecked()
        self.show_rotated_extended = self.rotated_extended_checkbox.isChecked()
        self.show_aligned_100 = self.aligned_100_checkbox.isChecked()
        self.show_aligned_extended = self.aligned_extended_checkbox.isChecked()
        self.show_polygon = self.polygon_checkbox.isChecked()
        current_region = global_context.get("selected_region")
        if current_region:
            self.on_region_changed(current_region)

    def update_map(self, context):
        """
        Obnoví mapu na základě aktuálních hodnot v global_context.
        To zahrnuje znovuvytvoření HTML obsahu s využitím nových hodnot bounding boxů.
        """
        try:
            # Získáváme aktuální region pro případnou regeneraci mapy
            region_name = context.get("selected_region", "N/A")
            if not region_name or region_name == "N/A":
                return
                
            # Aktualizujeme hodnotu extenze, pokud je k dispozici
            self.extension_percent = context.get("extension_percent", self.extension_percent)
            if self.extension_label:
                self.extension_label.setText(f"Hodnota extenze: {self.extension_percent}%")
                
            # Načteme aktuální bounding box hodnoty ze global_context
            bbox_rotated_100 = context.get("bbox_rotated_100", [])
            bbox_rotated_extended = context.get("bbox_rotated_extended", [])
            bbox_aligned_100 = context.get("bbox_aligned_100", [])
            bbox_aligned_extended = context.get("bbox_aligned_extended", [])
            
            # Načteme polygon ze shapefile
            polygon = self._load_polygon_from_shapefile(region_name)
            
            # Znovu vygenerujeme HTML obsah mapy
            html_content = self.build_map_html_content(
                region_name, polygon,
                bbox_rotated_100, bbox_rotated_extended,
                bbox_aligned_100, bbox_aligned_extended
            )
            html_file = self.generate_map_html_file(html_content)
            self.map_view.setUrl(QUrl.fromLocalFile(html_file))
        except Exception as e:
            logger.error(f"Chyba při aktualizaci mapy: {e}")
            
    def _load_polygon_from_shapefile(self, region_name):
        """Pomocná metoda pro načtení polygonu ze shapefile"""
        try:
            config = self.get_default_config()
            shapefile_dir = config.get("shapefile_dir")
            clean_name = sanitize_filename(region_name)
            shp_path = os.path.join(shapefile_dir, f"{clean_name}.shp")
            if not os.path.exists(shp_path):
                raise FileNotFoundError(f"Shapefile {shp_path} nebyl nalezen.")
            reader = shapefile.Reader(shp_path)
            shape_rec = reader.shape(0)
            return shape_rec.points
        except Exception as e:
            logger.error(f"Chyba při načítání shapefile: {e}")
            return []
            
    def on_region_changed(self, region_name: str):
        if not region_name:
            return
        try:
            self.region_label.setText(f"Vybraný region: {region_name}")
        except Exception as e:
            logger.error(f"Chyba při nastavování region labelu: {e}")
        self.extension_percent = global_context.get("extension_percent", self.extension_percent)
        if self.extension_label:
            self.extension_label.setText(f"Hodnota extenze: {self.extension_percent}%")

        bbox_rotated_100 = global_context.get("bbox_rotated_100", [])
        bbox_rotated_extended = global_context.get("bbox_rotated_extended", [])
        bbox_aligned_100 = global_context.get("bbox_aligned_100", [])
        bbox_aligned_extended = global_context.get("bbox_aligned_extended", [])
        try:
            config = self.get_default_config()
            shapefile_dir = config.get("shapefile_dir")
            clean_name = sanitize_filename(region_name)
            shp_path = os.path.join(shapefile_dir, f"{clean_name}.shp")
            if not os.path.exists(shp_path):
                raise FileNotFoundError(f"Shapefile {shp_path} nebyl nalezen.")
            reader = shapefile.Reader(shp_path)
            shape_rec = reader.shape(0)
            polygon = shape_rec.points
        except Exception as e:
            polygon = []
            logger.error(f"Chyba při načítání shapefile: {e}")
            QMessageBox.warning(None, "Chyba", f"Chyba při načítání shapefile: {e}")

        html_content = self.build_map_html_content(
            region_name, polygon,
            bbox_rotated_100, bbox_rotated_extended,
            bbox_aligned_100, bbox_aligned_extended
        )
        html_file = self.generate_map_html_file(html_content)
        # Nastavení URL s využitím QUrl
        self.map_view.setUrl(QUrl.fromLocalFile(html_file))

    def setup_ui(self, parent: QWidget) -> QWidget:
        widget = QWidget(parent)
        layout = QVBoxLayout(widget)

        title = QLabel("<h2>Interaktivní mapa</h2>", widget)
        layout.addWidget(title)

        info = QLabel(
            "Mapa využívá bounding box hodnoty z global_context. "
            "Zobrazuje čtyři varianty bboxů a skutečný tvar oblasti.",
            widget
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        self.region_label = QLabel("Vybraný region: N/A", widget)
        layout.addWidget(self.region_label)

        self.extension_label = QLabel(f"Hodnota extenze: {self.extension_percent}%", widget)
        layout.addWidget(self.extension_label)

        checkbox_group = QGroupBox("Zobrazení vrstev", widget)
        checkbox_layout = QVBoxLayout()

        self.rotated_100_checkbox = QCheckBox("Rotovaný bbox-100 (zelená)", widget)
        self.rotated_100_checkbox.setChecked(self.show_rotated_100)
        self.rotated_100_checkbox.stateChanged.connect(self.on_checkbox_changed)
        checkbox_layout.addWidget(self.rotated_100_checkbox)

        self.rotated_extended_checkbox = QCheckBox("Rotovaný extended bbox (modrá)", widget)
        self.rotated_extended_checkbox.setChecked(self.show_rotated_extended)
        self.rotated_extended_checkbox.stateChanged.connect(self.on_checkbox_changed)
        checkbox_layout.addWidget(self.rotated_extended_checkbox)

        self.aligned_100_checkbox = QCheckBox("Axis-aligned bbox-100 (fialová)", widget)
        self.aligned_100_checkbox.setChecked(self.show_aligned_100)
        self.aligned_100_checkbox.stateChanged.connect(self.on_checkbox_changed)
        checkbox_layout.addWidget(self.aligned_100_checkbox)

        self.aligned_extended_checkbox = QCheckBox("Axis-aligned extended bbox (oranžová)", widget)
        self.aligned_extended_checkbox.setChecked(self.show_aligned_extended)
        self.aligned_extended_checkbox.stateChanged.connect(self.on_checkbox_changed)
        checkbox_layout.addWidget(self.aligned_extended_checkbox)

        self.polygon_checkbox = QCheckBox("Skutečný tvar (červená)", widget)
        self.polygon_checkbox.setChecked(self.show_polygon)
        self.polygon_checkbox.stateChanged.connect(self.on_checkbox_changed)
        checkbox_layout.addWidget(self.polygon_checkbox)

        checkbox_group.setLayout(checkbox_layout)
        layout.addWidget(checkbox_group)

        self.map_view = QWebEngineView(widget)
        self.map_view.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
        self.map_view.settings().setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        self.map_view.setMinimumHeight(400)
        layout.addWidget(self.map_view)

        # Inicializace signálů – pokud již existuje vybraný region, provedeme zobrazení
        signal_manager.region_changed.connect(self.on_region_changed)
        signal_manager.global_context_updated.connect(self.update_map)
        current_region = global_context.get("selected_region")
        if current_region:
            self.on_region_changed(current_region)
        return widget

    def execute(self, data):
        # Neprovádí se žádná logika, metoda ponechána kvůli definici abstraktního rozhraní
        pass
