import sys
import os
from pathlib import Path

def get_resource_path(relative_path: str) -> Path:
    """
    Get effective path for a resource, compatible with both dev and PyInstaller frozen modes.
    
    Args:
        relative_path: Path relative to the project root (e.g. "assets/themes/apple_dark.qss")
        
    Returns:
        Absolute Path object to the resource.
    """
    if hasattr(sys, '_MEIPASS'):
        # PyInstaller creates a temporary directory _MEIPASS
        base_path = Path(sys._MEIPASS)
    else:
        # Normal dev environment
        # If this file is in utils/, project root is parent of parent
        base_path = Path(__file__).parent.parent
        
        # Fallback: if running from main.py, cwd might be project root
        if not (base_path / "assets").exists():
            base_path = Path(os.getcwd())
            
    return base_path / relative_path

def get_asset_path(asset_type: str, filename: str) -> Path:
    """Helper to get path for specific asset types e.g. ('themes', 'apple_dark.qss')"""
    return get_resource_path(os.path.join("assets", asset_type, filename))
