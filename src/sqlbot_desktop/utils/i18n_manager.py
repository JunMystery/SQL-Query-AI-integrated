"""Translation manager using tiered XML files for localization (i18n)."""

from __future__ import annotations
import os
import xml.etree.ElementTree as ET
from pathlib import Path
from PySide6.QtCore import QSettings

class I18nManager:
    """Manages multi-language translations across the application using strings.xml files."""
    
    _instance: I18nManager | None = None
    
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(I18nManager, cls).__new__(cls, *args, **kwargs)
            cls._instance._initialized = False
        return cls._instance
        
    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self.active_language = "vi"
        self.translations: dict[str, str] = {}
        self.load_preferred_language()
        
    def load_preferred_language(self) -> None:
        settings = QSettings("SQLBot", "SQLBotDesktop")
        lang = settings.value("language", "vi")
        self.load_language(lang)
        
    def load_language(self, lang_code: str) -> None:
        self.active_language = lang_code
        self.translations.clear()
        
        file_dir = Path(__file__).resolve().parent
        # The structure is src/sqlbot_desktop/utils/i18n_manager.py
        project_root = file_dir.parents[2]
        i18n_dir = project_root / "resources" / "i18n" / lang_code
        
        if not i18n_dir.exists():
            i18n_dir = Path("resources") / "i18n" / lang_code
            
        if not i18n_dir.exists():
            return
            
        for file in i18n_dir.glob("*.strings.xml"):
            prefix = file.name.split('.')[0] # e.g. "main" from "main.strings.xml"
            try:
                tree = ET.parse(file)
                root = tree.getroot()
                for string_node in root.findall("string"):
                    name = string_node.get("name")
                    if name:
                        text = string_node.text or ""
                        # Resolve key as prefix.name e.g. "main.app_title"
                        self.translations[f"{prefix}.{name}"] = text
            except Exception as e:
                print(f"Error parsing localization file {file}: {e}")

    def translate(self, key: str, default: str = "") -> str:
        """Returns the translation for the specified key, falling back to the default value if not found."""
        return self.translations.get(key, default or key)

# Helper functions
_manager = I18nManager()

def tr(key: str, default: str = "") -> str:
    return _manager.translate(key, default)

def set_language(lang_code: str) -> None:
    _manager.load_language(lang_code)
    settings = QSettings("SQLBot", "SQLBotDesktop")
    settings.setValue("language", lang_code)

def get_current_language() -> str:
    return _manager.active_language
