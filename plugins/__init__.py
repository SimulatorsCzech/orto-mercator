# File: /plugins/__init__.py
"""
Plugin package initialization file.
This file makes the 'plugins' directory a proper Python package,
allowing both absolute and relative imports to work correctly.
"""

# You can optionally define __all__ to control what is imported with "from plugins import *"
__all__ = [
    'VRTPlugin',
    'ColorCorrection',
    'ColorCorrectionDialog',
    'VRTCreationConfig',
    'VRTCreationWorker',
    'VRTProgressDialog'
]
