import os
import importlib.util
from typing import List, Dict, Any, Optional
from plugins.plugin_base import PluginBase

# Předem definované pořadí pluginů pro zobrazení v GUI
PREDEFINED_ORDER = [
    "UzemniCelkyInspirePlugin",
    "BBoxPlugin",
    "MapPlugin",
    "OrtofotoDownloadPlugin",
    "VRTCreationPlugin",
    "ReprojectionPlugin",
    "KonecnyOrezUzemiPlugin",
    "LoggingPlugin"
]

class PluginManager:
    def __init__(self, plugin_dir, app_config: Dict[str, Any] = None):
        self.plugin_dir = plugin_dir
        self.plugins = []
        self.app_config = app_config
        self.plugin_modules = {}

    def load_plugins(self, predefined_order=None):
        """
        Načte všechny pluginy z adresáře a seřadí je podle zadaného pořadí
        
        Args:
            predefined_order: Seznam názvů tříd pluginů v požadovaném pořadí
            
        Returns:
            Seznam načtených pluginů
        """
        self.plugins = []
        for file in os.listdir(self.plugin_dir):
            # Pokud se jedná o shapefile_clip_plugin, přeskočíme ho
            if file == "shapefile_clip_plugin.py" or file == "shapefile_clip_plugin":
                continue
            if file.endswith(".py") and file != "__init__.py":
                try:
                    # Dynamické načítání pluginu pomocí importlib
                    filepath = os.path.join(self.plugin_dir, file)
                    spec = importlib.util.spec_from_file_location(file[:-3], filepath)
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)
                    
                    # Hledání tříd pluginů v modulu
                    for attr_name in dir(mod):
                        attr = getattr(mod, attr_name)
                        if isinstance(attr, type) and issubclass(attr, PluginBase) and attr is not PluginBase:
                            # Vytvoříme instanci pluginu a předáme app_config
                            plugin_instance = attr(self.app_config) if self.app_config else attr()
                            self.plugins.append(plugin_instance)
                            self.plugin_modules[attr.__name__] = mod
                except Exception as e:
                    print(f"Chyba při načítání pluginu {file}: {str(e)}")
        
        # Seřazení pluginů podle zadaného pořadí nebo výchozího PREDEFINED_ORDER
        order = predefined_order if predefined_order is not None else PREDEFINED_ORDER
        self.plugins.sort(key=lambda p: order.index(p.__class__.__name__)
                          if p.__class__.__name__ in order else 999)
        
        return self.plugins
        
    def get_plugin(self, plugin_name: str) -> Optional[PluginBase]:
        """
        Vrátí plugin podle názvu.
        
        Args:
            plugin_name: Název pluginu
            
        Returns:
            Plugin nebo None, pokud plugin neexistuje
        """
        for plugin in self.plugins:
            if plugin.__class__.__name__ == plugin_name:
                return plugin
        
        return None
    
    def unload_plugins(self):
        """
        Uvolní všechny načtené pluginy.
        """
        for plugin in self.plugins:
            try:
                if hasattr(plugin, 'on_plugin_unloaded'):
                    plugin.on_plugin_unloaded()
            except Exception as e:
                print(f"Chyba při uvolňování pluginu {plugin.__class__.__name__}: {str(e)}")
        
        self.plugins = []
        self.plugin_modules = {}
