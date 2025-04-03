# plugin_base.py
"""
Abstraktní základ pro všechny pluginy použitý v aplikaci.
Plugin by měl implementovat minimálně následující metody:

- name()         => Vrací název pluginu jako řetězec.
- description()  => Vrací stručný popis funkčnosti pluginu.
- get_default_config() => Vrací výchozí konfiguraci pluginu jako slovník.
- update_config(new_config) => Umožňuje aktualizovat konfiguraci.
- setup_ui(parent) => Vytváří a vrací widget s uživatelským rozhraním.
- execute(data)  => Metoda, která spouští logiku pluginu (pokud je třeba).
"""

class PluginBase:
    def name(self) -> str:
        """Vrací název pluginu."""
        raise NotImplementedError("Metoda name() musí být implementována.")

    def description(self) -> str:
        """Vrací popis pluginu."""
        raise NotImplementedError("Metoda description() musí být implementována.")

    def get_default_config(self) -> dict:
        """Vrací výchozí konfiguraci pluginu."""
        raise NotImplementedError("Metoda get_default_config() musí být implementována.")

    def update_config(self, new_config: dict):
        """Aktualizuje konfiguraci pluginu."""
        raise NotImplementedError("Metoda update_config() musí být implementována.")

    def setup_ui(self, parent) -> object:
        """
        Vytváří uživatelské rozhraní pluginu.
        
        Parametry:
          parent: Rodičovský widget.
          
        Návratová hodnota:
          Widget obsahující UI pluginu.
        """
        raise NotImplementedError("Metoda setup_ui() musí být implementována.")

    def execute(self, data):
        """Spouští logiku pluginu; není vždy potřeba."""
        raise NotImplementedError("Metoda execute() musí být implementována.")