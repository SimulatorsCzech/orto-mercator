"""
Modul obsahující třídu pro rotaci log souborů.
"""

import os
import time
import glob
import logging
from typing import List, Optional
from datetime import datetime

class LogRotationHandler(logging.Handler):
    """
    Handler pro rotaci log souborů.
    Automaticky rotuje soubory podle velikosti nebo času.
    """
    
    def __init__(self, filename: str, max_bytes: int = 10*1024*1024, backup_count: int = 5, 
                 encoding: str = 'utf-8'):
        """
        Inicializace handleru.
        
        Args:
            filename: Cesta k log souboru
            max_bytes: Maximální velikost souboru v bajtech (výchozí 10 MB)
            backup_count: Maximální počet záložních souborů (výchozí 5)
            encoding: Kódování souboru (výchozí utf-8)
        """
        super().__init__()
        
        self.filename = filename
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self.encoding = encoding
        
        # Vytvoříme adresář pro logy, pokud neexistuje
        os.makedirs(os.path.dirname(self.filename), exist_ok=True)
        
        # Otevřeme soubor
        self.stream = self._open()
    
    def _open(self):
        """
        Otevře log soubor.
        
        Returns:
            Otevřený soubor
        """
        return open(self.filename, 'a', encoding=self.encoding)
    
    def emit(self, record: logging.LogRecord) -> None:
        """
        Zapíše záznam do logu.
        
        Args:
            record: Záznam logu
        """
        try:
            # Zkontrolujeme, zda je potřeba rotovat soubor
            if self.should_rollover():
                self.do_rollover()
            
            # Formátujeme záznam
            msg = self.format(record)
            
            # Zapíšeme záznam do souboru
            self.stream.write(msg + '\n')
            self.stream.flush()
        except Exception:
            self.handleError(record)
    
    def should_rollover(self) -> bool:
        """
        Zkontroluje, zda je potřeba rotovat soubor.
        
        Returns:
            True pokud je potřeba rotovat soubor, jinak False
        """
        if self.max_bytes <= 0:
            return False
        
        # Zjistíme velikost souboru
        try:
            if os.path.exists(self.filename):
                return os.path.getsize(self.filename) >= self.max_bytes
        except Exception:
            pass
        
        return False
    
    def do_rollover(self) -> None:
        """
        Provede rotaci souboru.
        """
        # Zavřeme aktuální soubor
        if self.stream:
            self.stream.close()
            self.stream = None
        
        # Pokud máme záložní soubory, posuneme je
        if self.backup_count > 0:
            # Odstraníme nejstarší soubor
            if os.path.exists(f"{self.filename}.{self.backup_count}"):
                os.remove(f"{self.filename}.{self.backup_count}")
            
            # Posuneme ostatní soubory
            for i in range(self.backup_count - 1, 0, -1):
                src = f"{self.filename}.{i}"
                dst = f"{self.filename}.{i + 1}"
                
                if os.path.exists(src):
                    if os.path.exists(dst):
                        os.remove(dst)
                    os.rename(src, dst)
            
            # Přejmenujeme aktuální soubor
            if os.path.exists(self.filename):
                os.rename(self.filename, f"{self.filename}.1")
        
        # Otevřeme nový soubor
        self.stream = self._open()
    
    def close(self) -> None:
        """
        Zavře handler.
        """
        if self.stream:
            self.stream.close()
            self.stream = None
        
        super().close()

class TimeBasedLogRotationHandler(LogRotationHandler):
    """
    Handler pro rotaci log souborů podle času.
    Automaticky rotuje soubory podle času (denně, týdně, měsíčně).
    """
    
    # Konstanty pro interval rotace
    DAILY = 'daily'
    WEEKLY = 'weekly'
    MONTHLY = 'monthly'
    
    def __init__(self, filename: str, interval: str = DAILY, backup_count: int = 5, 
                 encoding: str = 'utf-8'):
        """
        Inicializace handleru.
        
        Args:
            filename: Cesta k log souboru
            interval: Interval rotace (daily, weekly, monthly)
            backup_count: Maximální počet záložních souborů (výchozí 5)
            encoding: Kódování souboru (výchozí utf-8)
        """
        super().__init__(filename, 0, backup_count, encoding)
        
        self.interval = interval
        self.last_rollover = self._get_rollover_time()
    
    def _get_rollover_time(self) -> float:
        """
        Vrátí čas poslední rotace.
        
        Returns:
            Čas poslední rotace (timestamp)
        """
        if not os.path.exists(self.filename):
            return 0
        
        # Zjistíme čas poslední modifikace souboru
        return os.path.getmtime(self.filename)
    
    def should_rollover(self) -> bool:
        """
        Zkontroluje, zda je potřeba rotovat soubor.
        
        Returns:
            True pokud je potřeba rotovat soubor, jinak False
        """
        # Zjistíme aktuální čas
        now = time.time()
        
        # Zjistíme čas poslední rotace
        if self.last_rollover == 0:
            self.last_rollover = now
            return False
        
        # Zjistíme, zda je potřeba rotovat soubor
        if self.interval == self.DAILY:
            # Denní rotace - kontrolujeme, zda jsme v novém dni
            last_day = datetime.fromtimestamp(self.last_rollover).day
            current_day = datetime.fromtimestamp(now).day
            return last_day != current_day
        
        elif self.interval == self.WEEKLY:
            # Týdenní rotace - kontrolujeme, zda jsme v novém týdnu
            last_week = datetime.fromtimestamp(self.last_rollover).isocalendar()[1]
            current_week = datetime.fromtimestamp(now).isocalendar()[1]
            return last_week != current_week
        
        elif self.interval == self.MONTHLY:
            # Měsíční rotace - kontrolujeme, zda jsme v novém měsíci
            last_month = datetime.fromtimestamp(self.last_rollover).month
            current_month = datetime.fromtimestamp(now).month
            return last_month != current_month
        
        return False
    
    def do_rollover(self) -> None:
        """
        Provede rotaci souboru.
        """
        # Provedeme rotaci
        super().do_rollover()
        
        # Aktualizujeme čas poslední rotace
        self.last_rollover = time.time()

def cleanup_old_logs(log_dir: str, pattern: str = "*.log*", max_age_days: int = 30) -> int:
    """
    Vyčistí staré log soubory.
    
    Args:
        log_dir: Adresář s logy
        pattern: Vzor pro vyhledávání souborů
        max_age_days: Maximální stáří souborů ve dnech
        
    Returns:
        Počet odstraněných souborů
    """
    # Zjistíme aktuální čas
    now = time.time()
    
    # Zjistíme maximální stáří souborů
    max_age = max_age_days * 24 * 60 * 60  # dny na sekundy
    
    # Najdeme všechny soubory
    files = glob.glob(os.path.join(log_dir, pattern))
    
    # Odstraníme staré soubory
    removed_count = 0
    for file in files:
        # Zjistíme stáří souboru
        file_age = now - os.path.getmtime(file)
        
        # Pokud je soubor starší než maximální stáří, odstraníme ho
        if file_age > max_age:
            try:
                os.remove(file)
                removed_count += 1
            except Exception as e:
                print(f"Chyba při odstraňování souboru {file}: {str(e)}")
    
    return removed_count