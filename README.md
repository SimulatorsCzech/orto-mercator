# Modernizovaný BBox Plugin

Modernizovaná verze BBox pluginu s vylepšeným uživatelským rozhraním a novými funkcemi.

## Funkce

- Moderní uživatelské rozhraní s intuitivním ovládáním
- Více způsobů zadávání bounding boxu (souřadnice, střed a rozměry)
- Interaktivní mapa pro vizualizaci a úpravu bounding boxu
- Podpora více formátů exportu (WKT, GeoJSON, Shapefile, CSV)
- Podpora více souřadnicových systémů
- Generování reportů ve formátech HTML a PDF
- Měření vzdáleností a ploch na mapě
- Kreslení bodů, linií a polygonů na mapě

## Instalace

### Automatická instalace

Pro automatickou instalaci a spuštění modernizovaného BBox pluginu stačí spustit skript `run_modernized_bbox.py`:

```bash
python run_modernized_bbox.py
```

Tento skript automaticky:
1. Vytvoří potřebnou adresářovou strukturu
2. Vytvoří dummy BBox plugin, pokud neexistuje
3. Vytvoří integrační soubor pro propojení původního a modernizovaného pluginu
4. Vytvoří potřebné inicializační soubory
5. Vytvoří hlavní aplikaci pro spuštění pluginu
6. Spustí aplikaci

### Ruční instalace

Pokud chcete provést instalaci ručně, postupujte podle následujících kroků:

1. Vytvořte adresářovou strukturu:
   ```
   plugins/
   ├── bbox_plugin/
   │   ├── __init__.py
   │   ├── bbox_plugin.py
   │   └── bbox_plugin_modernized_integration.py
   └── bbox_plugin_modernized/
       ├── __init__.py
       ├── bbox_plugin_adapter.py
       ├── bbox_ui_manager.py
       ├── bbox_controls_panel.py
       ├── bbox_visualization.py
       ├── bbox_results_panel.py
       ├── bbox_web_handler.py
       ├── bbox_clipboard_utils.py
       ├── bbox_export_utils.py
       ├── bbox_template_utils.py
       ├── bbox_report_utils.py
       ├── map.html
       ├── templates/
       │   ├── export/
       │   ├── reports/
       │   └── ui/
       └── static/
           ├── css/
           ├── js/
           └── images/
   ```

2. Zkopírujte všechny soubory do příslušných adresářů.

3. Vytvořte integrační soubor `bbox_plugin_modernized_integration.py` v adresáři `plugins/bbox_plugin/`.

4. Upravte původní BBox plugin podle instrukcí v souboru `bbox_plugin_update.py`.

5. Vytvořte hlavní aplikaci `main_app.py` pro spuštění pluginu.

## Použití

Po instalaci můžete spustit aplikaci pomocí příkazu:

```bash
python main_app.py
```

### Vytvoření bounding boxu

Bounding box můžete vytvořit několika způsoby:

1. **Zadáním souřadnic:**
   - Přejděte na záložku "Souřadnice"
   - Zadejte minimální a maximální souřadnice X a Y
   - Klikněte na tlačítko "Generovat Bounding Box"

2. **Zadáním středu a rozměrů:**
   - Přejděte na záložku "Střed a rozměry"
   - Zadejte souřadnice středu a rozměry bounding boxu
   - Klikněte na tlačítko "Generovat Bounding Box"

3. **Interaktivně na mapě:**
   - Klikněte na tlačítko kreslení obdélníku v nástrojové liště mapy
   - Klikněte a táhněte na mapě pro vytvoření bounding boxu

### Export bounding boxu

Bounding box můžete exportovat do různých formátů:

1. **Kopírování do schránky:**
   - Vyberte požadovaný formát v záložkách panelu výsledků
   - Klikněte na tlačítko "Kopírovat do schránky"

2. **Export do souboru:**
   - Klikněte na tlačítko "Exportovat"
   - Vyberte požadovaný formát z rozbalovacího menu
   - Vyberte umístění a název souboru v dialogu pro uložení

### Generování reportů

Plugin umožňuje generovat reporty o bounding boxu:

1. Klikněte na tlačítko "Exportovat" v panelu výsledků
2. Vyberte "Generovat report" z rozbalovacího menu
3. Vyberte formát reportu (HTML nebo PDF)
4. Vyberte umístění a název souboru v dialogu pro uložení

## Požadavky

- Python 3.6+
- PySide6 (Qt for Python)
- PySide6.QtWebEngineWidgets (pro mapu)
- Fiona a Shapely (pro export do Shapefile)
- ReportLab (pro generování PDF reportů)

## Licence

Tento projekt je licencován pod licencí MIT - viz soubor [LICENSE](LICENSE) pro více informací.