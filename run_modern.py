#!/usr/bin/env python3
import sys
import os

# Přidání adresáře projektu do sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Import a spuštění modernizované verze
from src.modernized.main import main

if __name__ == "__main__":
    main()