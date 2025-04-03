"""
Modul obsahující komponentu pro zobrazení statistik logů.
"""

from typing import Dict, List, Tuple
from collections import Counter
from datetime import datetime, timedelta

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                              QGroupBox, QTabWidget, QTableWidget, QTableWidgetItem,
                              QHeaderView)
from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QColor, QPainter, QBrush, QPen
from PySide6.QtCharts import QChart, QChartView, QPieSeries, QBarSeries, QBarSet, QBarCategoryAxis, QValueAxis

from plugins.logging.log_entry import LogEntry
from plugins.logging.log_manager import LogManager

class LogStatistics(QWidget):
    """
    Komponenta pro zobrazení statistik logů.
    """
    
    def __init__(self, log_manager: LogManager, parent: QWidget = None):
        """
        Inicializace komponenty pro statistiky.
        
        Args:
            log_manager: Správce logů
            parent: Rodičovský widget
        """
        super().__init__(parent)
        
        self.log_manager = log_manager
        
        # UI komponenty
        self.tabs = None
        self.level_chart_view = None
        self.source_chart_view = None
        self.time_chart_view = None
        self.level_table = None
        self.source_table = None
        
        # Vytvoření UI
        self._setup_ui()
        
        # Připojení signálů
        self._connect_signals()
        
        # Aktualizace statistik
        self.update_statistics()
    
    def _setup_ui(self):
        """
        Vytvoří uživatelské rozhraní.
        """
        # Vytvoření hlavního layoutu
        layout = QVBoxLayout(self)
        
        # Přidání titulku
        title = QLabel("<h2>Statistiky logů</h2>", self)
        layout.addWidget(title)
        
        # Přidání informačního textu
        info = QLabel("Statistiky a analýza logů v aplikaci.", self)
        info.setWordWrap(True)
        layout.addWidget(info)
        
        # Vytvoření záložek
        self.tabs = QTabWidget(self)
        
        # Záložka pro grafy
        charts_widget = QWidget(self)
        charts_layout = QVBoxLayout(charts_widget)
        
        # Graf pro úrovně logů
        level_group = QGroupBox("Rozdělení podle úrovně", self)
        level_layout = QVBoxLayout()
        self.level_chart_view = QChartView(self)
        self.level_chart_view.setRenderHint(QPainter.Antialiasing)
        level_layout.addWidget(self.level_chart_view)
        level_group.setLayout(level_layout)
        charts_layout.addWidget(level_group)
        
        # Graf pro zdroje logů
        source_group = QGroupBox("Rozdělení podle zdroje", self)
        source_layout = QVBoxLayout()
        self.source_chart_view = QChartView(self)
        self.source_chart_view.setRenderHint(QPainter.Antialiasing)
        source_layout.addWidget(self.source_chart_view)
        source_group.setLayout(source_layout)
        charts_layout.addWidget(source_group)
        
        # Graf pro časový průběh
        time_group = QGroupBox("Časový průběh", self)
        time_layout = QVBoxLayout()
        self.time_chart_view = QChartView(self)
        self.time_chart_view.setRenderHint(QPainter.Antialiasing)
        time_layout.addWidget(self.time_chart_view)
        time_group.setLayout(time_layout)
        charts_layout.addWidget(time_group)
        
        self.tabs.addTab(charts_widget, "Grafy")
        
        # Záložka pro tabulky
        tables_widget = QWidget(self)
        tables_layout = QVBoxLayout(tables_widget)
        
        # Tabulka pro úrovně logů
        level_table_group = QGroupBox("Počty podle úrovně", self)
        level_table_layout = QVBoxLayout()
        self.level_table = QTableWidget(0, 2, self)
        self.level_table.setHorizontalHeaderLabels(["Úroveň", "Počet"])
        self.level_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.level_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        level_table_layout.addWidget(self.level_table)
        level_table_group.setLayout(level_table_layout)
        tables_layout.addWidget(level_table_group)
        
        # Tabulka pro zdroje logů
        source_table_group = QGroupBox("Počty podle zdroje", self)
        source_table_layout = QVBoxLayout()
        self.source_table = QTableWidget(0, 2, self)
        self.source_table.setHorizontalHeaderLabels(["Zdroj", "Počet"])
        self.source_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.source_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        source_table_layout.addWidget(self.source_table)
        source_table_group.setLayout(source_table_layout)
        tables_layout.addWidget(source_table_group)
        
        self.tabs.addTab(tables_widget, "Tabulky")
        
        layout.addWidget(self.tabs)
    
    def _connect_signals(self):
        """
        Připojí signály k příslušným slotům.
        """
        # Připojení signálu pro přidání nového logu
        self.log_manager.log_added.connect(self._on_log_added)
    
    def _on_log_added(self, log_entry: LogEntry):
        """
        Slot volaný při přidání nového logu.
        
        Args:
            log_entry: Nový záznam logu
        """
        # Aktualizujeme statistiky
        self.update_statistics()
    
    def update_statistics(self):
        """
        Aktualizuje statistiky logů.
        """
        # Získáme všechny logy
        logs = self.log_manager.get_filtered_logs()
        
        # Aktualizujeme grafy
        self._update_level_chart(logs)
        self._update_source_chart(logs)
        self._update_time_chart(logs)
        
        # Aktualizujeme tabulky
        self._update_level_table(logs)
        self._update_source_table(logs)
    
    def _update_level_chart(self, logs: List[LogEntry]):
        """
        Aktualizuje graf pro úrovně logů.
        
        Args:
            logs: Seznam záznamů logů
        """
        # Vytvoříme nový graf
        chart = QChart()
        chart.setTitle("Rozdělení logů podle úrovně")
        chart.setAnimationOptions(QChart.SeriesAnimations)
        
        # Vytvoříme sérii pro koláčový graf
        series = QPieSeries()
        
        # Počítáme výskyty jednotlivých úrovní
        level_counts = Counter([log.level for log in logs])
        
        # Přidáme data do série
        for level, count in level_counts.items():
            slice = series.append(f"{level} ({count})", count)
            
            # Nastavíme barvu podle úrovně
            if level == "DEBUG":
                slice.setBrush(QColor(100, 100, 100))
            elif level == "INFO":
                slice.setBrush(QColor(0, 0, 0))
            elif level == "WARNING":
                slice.setBrush(QColor(255, 165, 0))
            elif level == "ERROR":
                slice.setBrush(QColor(255, 0, 0))
            elif level == "CRITICAL":
                slice.setBrush(QColor(139, 0, 0))
        
        # Přidáme sérii do grafu
        chart.addSeries(series)
        
        # Nastavíme graf do view
        self.level_chart_view.setChart(chart)
    
    def _update_source_chart(self, logs: List[LogEntry]):
        """
        Aktualizuje graf pro zdroje logů.
        
        Args:
            logs: Seznam záznamů logů
        """
        # Vytvoříme nový graf
        chart = QChart()
        chart.setTitle("Rozdělení logů podle zdroje")
        chart.setAnimationOptions(QChart.SeriesAnimations)
        
        # Počítáme výskyty jednotlivých zdrojů
        source_counts = Counter([log.source for log in logs])
        
        # Vytvoříme sérii pro sloupcový graf
        bar_set = QBarSet("Počet logů")
        
        # Přidáme data do série
        categories = []
        for source, count in source_counts.most_common(10):  # Omezíme na 10 nejčastějších zdrojů
            bar_set.append(count)
            categories.append(source)
        
        # Vytvoříme sérii
        series = QBarSeries()
        series.append(bar_set)
        
        # Přidáme sérii do grafu
        chart.addSeries(series)
        
        # Vytvoříme osy
        axis_x = QBarCategoryAxis()
        axis_x.append(categories)
        chart.addAxis(axis_x, Qt.AlignBottom)
        series.attachAxis(axis_x)
        
        axis_y = QValueAxis()
        axis_y.setRange(0, max(source_counts.values()) if source_counts else 10)
        chart.addAxis(axis_y, Qt.AlignLeft)
        series.attachAxis(axis_y)
        
        # Nastavíme legendu
        chart.legend().setVisible(False)
        
        # Nastavíme graf do view
        self.source_chart_view.setChart(chart)
    
    def _update_time_chart(self, logs: List[LogEntry]):
        """
        Aktualizuje graf pro časový průběh logů.
        
        Args:
            logs: Seznam záznamů logů
        """
        # Vytvoříme nový graf
        chart = QChart()
        chart.setTitle("Časový průběh logů")
        chart.setAnimationOptions(QChart.SeriesAnimations)
        
        # Pokud nemáme žádné logy, vrátíme prázdný graf
        if not logs:
            self.time_chart_view.setChart(chart)
            return
        
        # Získáme časový rozsah
        now = datetime.now()
        start_time = now - timedelta(hours=1)  # Poslední hodina
        
        # Rozdělíme časový rozsah na 10 intervalů
        interval = timedelta(minutes=6)  # 6 minut = 1 hodina / 10
        
        # Vytvoříme intervaly
        intervals = []
        current_time = start_time
        while current_time <= now:
            intervals.append((current_time, current_time + interval))
            current_time += interval
        
        # Počítáme výskyty logů v jednotlivých intervalech
        interval_counts = {i: 0 for i in range(len(intervals))}
        for log in logs:
            for i, (start, end) in enumerate(intervals):
                if start <= log.timestamp <= end:
                    interval_counts[i] += 1
                    break
        
        # Vytvoříme sérii pro sloupcový graf
        bar_set = QBarSet("Počet logů")
        
        # Přidáme data do série
        for i in range(len(intervals)):
            bar_set.append(interval_counts[i])
        
        # Vytvoříme sérii
        series = QBarSeries()
        series.append(bar_set)
        
        # Přidáme sérii do grafu
        chart.addSeries(series)
        
        # Vytvoříme osy
        axis_x = QBarCategoryAxis()
        axis_x.append([intervals[i][0].strftime("%H:%M") for i in range(len(intervals))])
        chart.addAxis(axis_x, Qt.AlignBottom)
        series.attachAxis(axis_x)
        
        axis_y = QValueAxis()
        axis_y.setRange(0, max(interval_counts.values()) if interval_counts else 10)
        chart.addAxis(axis_y, Qt.AlignLeft)
        series.attachAxis(axis_y)
        
        # Nastavíme legendu
        chart.legend().setVisible(False)
        
        # Nastavíme graf do view
        self.time_chart_view.setChart(chart)
    
    def _update_level_table(self, logs: List[LogEntry]):
        """
        Aktualizuje tabulku pro úrovně logů.
        
        Args:
            logs: Seznam záznamů logů
        """
        # Počítáme výskyty jednotlivých úrovní
        level_counts = Counter([log.level for log in logs])
        
        # Nastavíme počet řádků
        self.level_table.setRowCount(len(level_counts))
        
        # Přidáme data do tabulky
        for i, (level, count) in enumerate(level_counts.most_common()):
            # Přidáme úroveň
            level_item = QTableWidgetItem(level)
            self.level_table.setItem(i, 0, level_item)
            
            # Přidáme počet
            count_item = QTableWidgetItem(str(count))
            count_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.level_table.setItem(i, 1, count_item)
            
            # Nastavíme barvu podle úrovně
            color = QColor(0, 0, 0)
            if level == "DEBUG":
                color = QColor(100, 100, 100)
            elif level == "INFO":
                color = QColor(0, 0, 0)
            elif level == "WARNING":
                color = QColor(255, 165, 0)
            elif level == "ERROR":
                color = QColor(255, 0, 0)
            elif level == "CRITICAL":
                color = QColor(139, 0, 0)
            
            level_item.setForeground(color)
            count_item.setForeground(color)
    
    def _update_source_table(self, logs: List[LogEntry]):
        """
        Aktualizuje tabulku pro zdroje logů.
        
        Args:
            logs: Seznam záznamů logů
        """
        # Počítáme výskyty jednotlivých zdrojů
        source_counts = Counter([log.source for log in logs])
        
        # Nastavíme počet řádků
        self.source_table.setRowCount(len(source_counts))
        
        # Přidáme data do tabulky
        for i, (source, count) in enumerate(source_counts.most_common()):
            # Přidáme zdroj
            source_item = QTableWidgetItem(source)
            self.source_table.setItem(i, 0, source_item)
            
            # Přidáme počet
            count_item = QTableWidgetItem(str(count))
            count_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.source_table.setItem(i, 1, count_item)