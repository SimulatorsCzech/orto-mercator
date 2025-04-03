"""
Modul obsahující funkce pro export logů do různých formátů.
"""

import os
import csv
import json
from typing import List, Dict, Any
from datetime import datetime

from plugins.logging.log_entry import LogEntry

def export_to_csv(logs: List[LogEntry], file_path: str) -> bool:
    """
    Exportuje logy do CSV souboru.
    
    Args:
        logs: Seznam záznamů logů
        file_path: Cesta k souboru pro export
        
    Returns:
        True pokud se export podařil, jinak False
    """
    try:
        with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['timestamp', 'level', 'source', 'message']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            writer.writeheader()
            for log in logs:
                writer.writerow({
                    'timestamp': log.timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3],
                    'level': log.level,
                    'source': log.source,
                    'message': log.message
                })
        
        return True
    except Exception as e:
        print(f"Chyba při exportu do CSV: {str(e)}")
        return False

def export_to_html(logs: List[LogEntry], file_path: str) -> bool:
    """
    Exportuje logy do HTML souboru.
    
    Args:
        logs: Seznam záznamů logů
        file_path: Cesta k souboru pro export
        
    Returns:
        True pokud se export podařil, jinak False
    """
    try:
        with open(file_path, 'w', encoding='utf-8') as htmlfile:
            # Začátek HTML dokumentu
            htmlfile.write("""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Logy aplikace</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 20px;
        }
        h1 {
            color: #333;
        }
        table {
            border-collapse: collapse;
            width: 100%;
            margin-top: 20px;
        }
        th, td {
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
        }
        th {
            background-color: #f2f2f2;
            position: sticky;
            top: 0;
        }
        tr:nth-child(even) {
            background-color: #f9f9f9;
        }
        .debug {
            color: #666;
        }
        .info {
            color: #000;
        }
        .warning {
            color: #ff9900;
        }
        .error {
            color: #ff0000;
        }
        .critical {
            color: #8b0000;
        }
    </style>
</head>
<body>
    <h1>Logy aplikace</h1>
    <p>Exportováno: """ + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + """</p>
    <table>
        <thead>
            <tr>
                <th>Čas</th>
                <th>Úroveň</th>
                <th>Zdroj</th>
                <th>Zpráva</th>
            </tr>
        </thead>
        <tbody>
""")
            
            # Přidáme řádky pro jednotlivé logy
            for log in logs:
                level_class = log.level.lower()
                htmlfile.write(f"""            <tr class="{level_class}">
                <td>{log.timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}</td>
                <td>{log.level}</td>
                <td>{log.source}</td>
                <td>{log.message}</td>
            </tr>
""")
            
            # Konec HTML dokumentu
            htmlfile.write("""        </tbody>
    </table>
</body>
</html>
""")
        
        return True
    except Exception as e:
        print(f"Chyba při exportu do HTML: {str(e)}")
        return False

def export_to_json(logs: List[LogEntry], file_path: str) -> bool:
    """
    Exportuje logy do JSON souboru.
    
    Args:
        logs: Seznam záznamů logů
        file_path: Cesta k souboru pro export
        
    Returns:
        True pokud se export podařil, jinak False
    """
    try:
        # Převedeme logy na seznam slovníků
        logs_data = []
        for log in logs:
            logs_data.append({
                'timestamp': log.timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3],
                'level': log.level,
                'source': log.source,
                'message': log.message
            })
        
        # Vytvoříme výsledný JSON
        data = {
            'exported_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'logs_count': len(logs),
            'logs': logs_data
        }
        
        # Zapíšeme do souboru
        with open(file_path, 'w', encoding='utf-8') as jsonfile:
            json.dump(data, jsonfile, indent=2, ensure_ascii=False)
        
        return True
    except Exception as e:
        print(f"Chyba při exportu do JSON: {str(e)}")
        return False

class LogExporter:
    """
    Třída pro export logů do různých formátů.
    """
    
    @staticmethod
    def export(logs: List[LogEntry], file_path: str) -> bool:
        """
        Exportuje logy do souboru podle přípony.
        
        Args:
            logs: Seznam záznamů logů
            file_path: Cesta k souboru pro export
            
        Returns:
            True pokud se export podařil, jinak False
        """
        # Zjistíme příponu souboru
        _, ext = os.path.splitext(file_path)
        ext = ext.lower()
        
        # Exportujeme podle přípony
        if ext == '.csv':
            return export_to_csv(logs, file_path)
        elif ext == '.html' or ext == '.htm':
            return export_to_html(logs, file_path)
        elif ext == '.json':
            return export_to_json(logs, file_path)
        elif ext == '.log' or ext == '.txt':
            # Jednoduchý textový export
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    for log in logs:
                        f.write(str(log) + '\n')
                return True
            except Exception as e:
                print(f"Chyba při exportu do textového souboru: {str(e)}")
                return False
        else:
            # Neznámý formát
            print(f"Neznámý formát souboru: {ext}")
            return False