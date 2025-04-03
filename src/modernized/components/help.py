from PySide6.QtWidgets import (QWidget, QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QTabWidget, QTextBrowser, QListWidget,
                             QListWidgetItem, QSplitter, QDialogButtonBox, QScrollArea,
                             QLineEdit)
from PySide6.QtCore import Qt, Signal, QUrl, QSize
from PySide6.QtGui import QFont, QIcon, QPixmap

class HelpComponent:
    """Komponenta nápovědy s interaktivním průvodcem a dokumentací"""
    
    def __init__(self, parent=None):
        self.parent = parent
        self.help_dialog = None
        
    def show_help(self, topic=None):
        """Zobrazí dialog nápovědy s volitelným tématem"""
        if not self.help_dialog:
            self.help_dialog = HelpDialog(self.parent)
            
        if topic:
            self.help_dialog.select_topic(topic)
            
        self.help_dialog.show()
        
    def show_quick_tour(self):
        """Zobrazí rychlého průvodce aplikací"""
        tour = QuickTourDialog(self.parent)
        tour.exec()
        
    def show_tooltip(self, widget, text):
        """Nastaví tooltip pro widget s formátovaným textem"""
        widget.setToolTip(text)
        widget.setToolTipDuration(5000)  # 5 sekund
        
class HelpDialog(QDialog):
    """Dialog nápovědy s vyhledáváním a obsahem"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Nápověda aplikace")
        self.resize(800, 600)
        self._init_ui()
        self._load_help_content()
        
    def _init_ui(self):
        # Hlavní layout
        layout = QVBoxLayout(self)
        
        # Záložky nápovědy
        self.tab_widget = QTabWidget()
        
        # Záložka obsahu
        content_tab = QWidget()
        content_layout = QVBoxLayout(content_tab)
        
        # Rozdělení na seznam témat a obsah
        splitter = QSplitter(Qt.Horizontal)
        
        # Seznam témat
        self.topic_list = QListWidget()
        self.topic_list.setMaximumWidth(250)
        self.topic_list.currentRowChanged.connect(self._show_topic)
        
        # Obsah tématu
        self.content_browser = QTextBrowser()
        self.content_browser.setOpenExternalLinks(True)
        
        splitter.addWidget(self.topic_list)
        splitter.addWidget(self.content_browser)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        
        content_layout.addWidget(splitter)
        
        # Záložka vyhledávání
        search_tab = QWidget()
        search_layout = QVBoxLayout(search_tab)
        
        # Vyhledávací pole
        search_box_layout = QHBoxLayout()
        search_label = QLabel("Hledat:")
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Zadejte hledaný výraz...")
        self.search_button = QPushButton("Hledat")
        
        search_box_layout.addWidget(search_label)
        search_box_layout.addWidget(self.search_edit, 1)
        search_box_layout.addWidget(self.search_button)
        
        # Výsledky vyhledávání
        self.search_results = QListWidget()
        
        search_layout.addLayout(search_box_layout)
        search_layout.addWidget(QLabel("Výsledky vyhledávání:"))
        search_layout.addWidget(self.search_results)
        
        # Propojení signálů pro vyhledávání
        self.search_button.clicked.connect(self._search_help)
        self.search_edit.returnPressed.connect(self._search_help)
        self.search_results.itemClicked.connect(self._show_search_result)
        
        # Přidání záložek
        self.tab_widget.addTab(content_tab, "Obsah")
        self.tab_widget.addTab(search_tab, "Vyhledávání")
        
        layout.addWidget(self.tab_widget)
        
        # Tlačítka
        button_box = QDialogButtonBox(QDialogButtonBox.Close)
        button_box.rejected.connect(self.close)
        layout.addWidget(button_box)
        
    def _load_help_content(self):
        """Načte obsah nápovědy"""
        # Přidání témat do seznamu
        topics = [
            {"id": "intro", "title": "Úvod do aplikace"},
            {"id": "interface", "title": "Uživatelské rozhraní"},
            {"id": "plugins", "title": "Práce s pluginy"},
            {"id": "maps", "title": "Práce s mapami"},
            {"id": "export", "title": "Export dat"},
            {"id": "shortcuts", "title": "Klávesové zkratky"},
            {"id": "faq", "title": "Často kladené otázky"},
        ]
        
        for topic in topics:
            item = QListWidgetItem(topic["title"])
            item.setData(Qt.UserRole, topic["id"])
            self.topic_list.addItem(item)
            
    def _show_topic(self, index):
        """Zobrazí obsah vybraného tématu"""
        if index < 0:
            return
            
        topic_id = self.topic_list.item(index).data(Qt.UserRole)
        self._load_topic_content(topic_id)
        
    def _load_topic_content(self, topic_id):
        """Načte obsah tématu podle ID"""
        # Zde by se normálně načítal obsah z HTML souborů nebo databáze
        # Pro ukázku používáme předpřipravený obsah
        
        content = {
            "intro": """
                <h1>Úvod do aplikace</h1>
                <p>Vítejte v aplikaci Orto Pokrokové - profesionální nástroj pro zpracování ortofoto snímků a geografických dat.</p>
                <p>Tato aplikace vám umožňuje:</p>
                <ul>
                    <li>Pracovat s mapovými podklady</li>
                    <li>Stahovat ortofoto snímky</li>
                    <li>Vytvářet VRT soubory</li>
                    <li>Provádět reprojekce</li>
                    <li>A mnoho dalšího...</li>
                </ul>
                <p>Pro začátek vyberte plugin v levém panelu a postupujte podle instrukcí.</p>
            """,
            "interface": """
                <h1>Uživatelské rozhraní</h1>
                <p>Aplikace se skládá z několika hlavních částí:</p>
                <ul>
                    <li><b>Levý panel</b> - seznam dostupných pluginů</li>
                    <li><b>Pravý panel</b> - obsah aktivního pluginu</li>
                    <li><b>Horní panel</b> - nástrojová lišta s akcemi</li>
                    <li><b>Dolní panel</b> - stavový řádek s informacemi</li>
                </ul>
                <p>Mezi pluginy můžete přepínat kliknutím na jejich název v levém panelu.</p>
            """,
            # Další témata by byla podobně definována
        }
        
        # Zobrazení obsahu nebo výchozí zprávy
        if topic_id in content:
            self.content_browser.setHtml(content[topic_id])
        else:
            self.content_browser.setHtml(f"<h1>Téma '{topic_id}' není k dispozici</h1><p>Obsah tohoto tématu se připravuje.</p>")
            
    def select_topic(self, topic_id):
        """Vybere téma podle ID"""
        # Najít index tématu v seznamu
        for i in range(self.topic_list.count()):
            if self.topic_list.item(i).data(Qt.UserRole) == topic_id:
                self.topic_list.setCurrentRow(i)
                self.tab_widget.setCurrentIndex(0)  # Přepnout na záložku obsahu
                return
                
        # Pokud téma nebylo nalezeno, zobrazit první téma
        if self.topic_list.count() > 0:
            self.topic_list.setCurrentRow(0)
            
    def _search_help(self):
        """Vyhledá v obsahu nápovědy"""
        search_text = self.search_edit.text().lower()
        if not search_text:
            return
            
        self.search_results.clear()
        
        # Simulace vyhledávání (v reálné aplikaci by se prohledával skutečný obsah)
        results = [
            {"id": "intro", "title": "Úvod do aplikace", "match": "aplikace, úvod, začátek"},
            {"id": "interface", "title": "Uživatelské rozhraní", "match": "rozhraní, panel, pluginy"},
            {"id": "plugins", "title": "Práce s pluginy", "match": "plugin, rozšíření, funkce"},
        ]
        
        # Filtrování výsledků
        filtered_results = []
        for result in results:
            if (search_text in result["title"].lower() or 
                search_text in result["match"].lower()):
                filtered_results.append(result)
                
        # Zobrazení výsledků
        for result in filtered_results:
            item = QListWidgetItem(result["title"])
            item.setData(Qt.UserRole, result["id"])
            self.search_results.addItem(item)
            
        # Přepnutí na záložku vyhledávání
        self.tab_widget.setCurrentIndex(1)
        
    def _show_search_result(self, item):
        """Zobrazí výsledek vyhledávání"""
        topic_id = item.data(Qt.UserRole)
        self._load_topic_content(topic_id)
        self.tab_widget.setCurrentIndex(0)  # Přepnout na záložku obsahu
        
        # Vybrat odpovídající téma v seznamu
        self.select_topic(topic_id)
        
class QuickTourDialog(QDialog):
    """Dialog s rychlým průvodcem aplikací"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Rychlý průvodce aplikací")
        self.resize(600, 400)
        self._init_ui()
        
    def _init_ui(self):
        # Hlavní layout
        layout = QVBoxLayout(self)
        
        # Obsah průvodce
        self.content_area = QScrollArea()
        self.content_area.setWidgetResizable(True)
        
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        
        # Přidání kroků průvodce
        steps = [
            {"title": "Vítejte v aplikaci", 
             "text": "Tato aplikace vám umožňuje pracovat s geografickými daty a ortofoto snímky."},
            {"title": "Výběr pluginu", 
             "text": "V levém panelu vyberte plugin, se kterým chcete pracovat."},
            {"title": "Nastavení parametrů", 
             "text": "Nastavte parametry podle vašich potřeb v hlavním panelu."},
            {"title": "Export výsledků", 
             "text": "Výsledky můžete exportovat pomocí tlačítka v horní liště."},
        ]
        
        for i, step in enumerate(steps):
            step_widget = QWidget()
            step_layout = QHBoxLayout(step_widget)
            
            # Číslo kroku
            number_label = QLabel(str(i+1))
            number_label.setAlignment(Qt.AlignCenter)
            number_label.setStyleSheet("""
                background-color: #2196F3;
                color: white;
                border-radius: 15px;
                min-width: 30px;
                min-height: 30px;
                max-width: 30px;
                max-height: 30px;
                font-weight: bold;
            """)
            
            # Obsah kroku
            step_content = QWidget()
            step_content_layout = QVBoxLayout(step_content)
            
            title_label = QLabel(step["title"])
            title_label.setFont(QFont("Segoe UI", 12, QFont.Bold))
            
            text_label = QLabel(step["text"])
            text_label.setWordWrap(True)
            
            step_content_layout.addWidget(title_label)
            step_content_layout.addWidget(text_label)
            
            step_layout.addWidget(number_label)
            step_layout.addWidget(step_content, 1)
            
            content_layout.addWidget(step_widget)
            
        # Přidání mezery na konci
        content_layout.addStretch(1)
        
        self.content_area.setWidget(content_widget)
        layout.addWidget(self.content_area)
        
        # Tlačítka
        button_box = QDialogButtonBox(QDialogButtonBox.Ok)
        button_box.accepted.connect(self.accept)
        layout.addWidget(button_box)
