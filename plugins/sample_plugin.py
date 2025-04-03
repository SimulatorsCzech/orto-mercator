# File: /plugins/sample_plugin.py
# Název souboru: sample_plugin.py
# Popis: Ukázkový plugin demonstrující základní nastavení konfigurace pomocí GUI ve frameworku PySide6.
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QMessageBox, QFormLayout, QLineEdit
from plugins.plugin_base import PluginBase

class SamplePlugin(PluginBase):
    """
    Ukázkový plugin demonstrující nastavitelný GUI formulář.
    Tento plugin obsahuje výchozí konfiguraci a umožňuje ji měnit prostřednictvím GUI prvků.
    """

    def __init__(self):
        # Výchozí konfigurace pluginu
        self.config = {
            "format": "png",          # Výchozí obrazový formát
            "process_method": "standard"   # Výchozí metoda zpracování
        }

    def name(self) -> str:
        return "Ukázkový plugin"

    def description(self) -> str:
        return "Plugin demonstrující úpravu konfigurace s předdefinovanými hodnotami a možností nastavit parametrické volby."

    def get_default_config(self) -> dict:
        return self.config

    def update_config(self, new_config: dict):
        self.config.update(new_config)

    def setup_ui(self, parent: QWidget) -> QWidget:
        widget = QWidget(parent)
        layout = QVBoxLayout(widget)
        
        # Přehledný titulek a popis
        title = QLabel("<h2>Konfigurace Pluginu</h2>", widget)
        layout.addWidget(title)
        desc = QLabel(self.description(), widget)
        layout.addWidget(desc)

        # Vytvoříme formulář na úpravu konfigurace
        form_layout = QFormLayout()
        self.format_input = QLineEdit(widget)
        self.format_input.setText(self.config.get("format", ""))
        form_layout.addRow("Obrazový formát:", self.format_input)
        
        self.method_input = QLineEdit(widget)
        self.method_input.setText(self.config.get("process_method", ""))
        form_layout.addRow("Metoda zpracování:", self.method_input)
        
        layout.addLayout(form_layout)

        # Tlačítko pro uložení konfigurace
        save_button = QPushButton("Uložit konfiguraci", widget)
        save_button.clicked.connect(self.save_config)
        layout.addWidget(save_button)

        # Tlačítko pro spuštění akce pluginu
        run_button = QPushButton("Spustit akci", widget)
        run_button.clicked.connect(lambda: self.execute(None))
        layout.addWidget(run_button)

        return widget

    def save_config(self):
        # Přečteme data z formuláře a aktualizujeme konfiguraci
        new_config = {
            "format": self.format_input.text(),
            "process_method": self.method_input.text()
        }
        self.update_config(new_config)
        QMessageBox.information(None, "Konfigurace uložena", "Nová konfigurace byla úspěšně uložena.")

    def execute(self, data):
        # Pro jednoduchost ukážeme pouze výpis aktuální konfigurace
        config_info = f"Formát: {self.config.get('format')}\nMetoda: {self.config.get('process_method')}"
        QMessageBox.information(None, "Vykonávám akci", f"Spouštím akci s následující konfigurací:\n{config_info}")