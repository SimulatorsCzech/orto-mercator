"""
Modul pro práci s vlákny a asynchronními operacemi.
"""

import threading
import queue
import time
import traceback
from typing import Callable, Any, Dict, List, Optional, Tuple
from PySide6.QtCore import QObject, Signal, QThread, QTimer

class ThreadWorker(QObject):
    """
    Třída pro spouštění operací v samostatném vlákně.
    
    Příklad použití:
    ```python
    def long_running_task(progress_callback=None):
        # Dlouho trvající operace
        for i in range(100):
            time.sleep(0.1)
            if progress_callback:
                progress_callback.emit(i)
        return "Hotovo"
        
    worker = ThreadWorker(long_running_task)
    worker.signals.result.connect(lambda result: print(f"Výsledek: {result}"))
    worker.signals.progress.connect(lambda value: print(f"Průběh: {value}%"))
    worker.signals.error.connect(lambda error: print(f"Chyba: {error}"))
    worker.signals.finished.connect(lambda: print("Operace dokončena"))
    worker.start()
    ```
    """
    
    class WorkerSignals(QObject):
        """Signály pro komunikaci s hlavním vláknem"""
        started = Signal()
        finished = Signal()
        error = Signal(tuple)
        result = Signal(object)
        progress = Signal(int)
        status = Signal(str)
        
    def __init__(self, fn: Callable, *args, **kwargs):
        """
        Inicializace workeru.
        
        Args:
            fn: Funkce, která bude spuštěna v samostatném vlákně
            *args: Argumenty pro funkci
            **kwargs: Klíčové argumenty pro funkci
        """
        super().__init__()
        
        # Uložení funkce a argumentů
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        
        # Vytvoření signálů
        self.signals = self.WorkerSignals()
        
        # Vytvoření vlákna
        self.thread = QThread()
        self.moveToThread(self.thread)
        
        # Propojení signálů
        self.thread.started.connect(self._execute)
        self.signals.finished.connect(self.thread.quit)
        self.signals.finished.connect(self.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        
    def start(self):
        """Spustí vlákno"""
        self.thread.start()
        
    def _execute(self):
        """Spustí funkci v samostatném vlákně"""
        # Emitování signálu started
        self.signals.started.emit()
        
        try:
            # Přidání progress_callback do kwargs, pokud funkce podporuje progress_callback
            kwargs = self.kwargs
            if 'progress_callback' not in kwargs:
                kwargs['progress_callback'] = self.signals.progress
                
            # Přidání status_callback do kwargs, pokud funkce podporuje status_callback
            if 'status_callback' not in kwargs:
                kwargs['status_callback'] = self.signals.status
                
            # Spuštění funkce
            result = self.fn(*self.args, **kwargs)
            
            # Emitování výsledku
            self.signals.result.emit(result)
            
        except Exception as e:
            # Emitování chyby
            error_info = (str(e), traceback.format_exc())
            self.signals.error.emit(error_info)
            
        finally:
            # Emitování signálu finished
            self.signals.finished.emit()
            
class ThreadPool:
    """
    Třída pro správu více vláken.
    
    Příklad použití:
    ```python
    pool = ThreadPool(max_threads=4)
    
    def task1():
        time.sleep(1)
        return "Task 1 done"
        
    def task2():
        time.sleep(2)
        return "Task 2 done"
        
    pool.add_task(task1, on_result=lambda result: print(result))
    pool.add_task(task2, on_result=lambda result: print(result))
    ```
    """
    
    def __init__(self, max_threads: int = 4):
        """
        Inicializace thread poolu.
        
        Args:
            max_threads: Maximální počet současně běžících vláken
        """
        self.max_threads = max_threads
        self.active_workers = []
        self.task_queue = queue.Queue()
        self.timer = QTimer()
        self.timer.timeout.connect(self._process_queue)
        self.timer.start(100)  # Kontrola fronty každých 100 ms
        
    def add_task(self, fn: Callable, *args, 
                 on_result: Optional[Callable] = None,
                 on_error: Optional[Callable] = None,
                 on_progress: Optional[Callable] = None,
                 on_finished: Optional[Callable] = None,
                 **kwargs) -> ThreadWorker:
        """
        Přidá úkol do fronty.
        
        Args:
            fn: Funkce, která bude spuštěna v samostatném vlákně
            *args: Argumenty pro funkci
            on_result: Callback pro výsledek
            on_error: Callback pro chybu
            on_progress: Callback pro průběh
            on_finished: Callback pro dokončení
            **kwargs: Klíčové argumenty pro funkci
            
        Returns:
            ThreadWorker: Instance workeru
        """
        # Vytvoření workeru
        worker = ThreadWorker(fn, *args, **kwargs)
        
        # Propojení callbacků
        if on_result:
            worker.signals.result.connect(on_result)
        if on_error:
            worker.signals.error.connect(on_error)
        if on_progress:
            worker.signals.progress.connect(on_progress)
        if on_finished:
            worker.signals.finished.connect(on_finished)
            
        # Přidání do fronty
        self.task_queue.put(worker)
        
        # Zpracování fronty
        self._process_queue()
        
        return worker
        
    def _process_queue(self):
        """Zpracuje frontu úkolů"""
        # Odstranění dokončených workerů
        self.active_workers = [w for w in self.active_workers if w.thread.isRunning()]
        
        # Spuštění nových workerů, pokud je místo
        while len(self.active_workers) < self.max_threads and not self.task_queue.empty():
            worker = self.task_queue.get()
            worker.signals.finished.connect(lambda w=worker: self._worker_finished(w))
            self.active_workers.append(worker)
            worker.start()
            
    def _worker_finished(self, worker: ThreadWorker):
        """Callback pro dokončení workeru"""
        if worker in self.active_workers:
            self.active_workers.remove(worker)
            
    def wait_for_all(self, timeout: Optional[float] = None) -> bool:
        """
        Čeká na dokončení všech úkolů.
        
        Args:
            timeout: Timeout v sekundách
            
        Returns:
            bool: True, pokud byly všechny úkoly dokončeny, False pokud vypršel timeout
        """
        start_time = time.time()
        
        while not self.task_queue.empty() or self.active_workers:
            # Kontrola timeoutu
            if timeout is not None and time.time() - start_time > timeout:
                return False
                
            # Zpracování fronty
            self._process_queue()
            
            # Pauza
            time.sleep(0.1)
            
        return True
        
    def cancel_all(self):
        """Zruší všechny úkoly"""
        # Vyprázdnění fronty
        while not self.task_queue.empty():
            try:
                self.task_queue.get_nowait()
            except queue.Empty:
                break
                
        # Ukončení běžících workerů
        for worker in self.active_workers:
            if worker.thread.isRunning():
                worker.thread.quit()
                worker.thread.wait(1000)  # Čekání max 1 sekundu
                
        self.active_workers = []