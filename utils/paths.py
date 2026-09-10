"""
utils/paths.py
Gestion des chemins, ressources (icônes de classe, SVG), thèmes QSS et QSettings.
Compatible exécution script standard et exécutable PyInstaller (_MEIPASS).
"""

import os
import sys
from typing import Optional
from PySide6 import QtWidgets, QtGui
from PySide6.QtCore import QSettings

SETTINGS_ORG = "Kilian"
SETTINGS_APP = "DofusOrganizer"


def get_app_settings() -> QSettings:
    """Retourne l'instance de configuration QSettings de l'application."""
    return QSettings(SETTINGS_ORG, SETTINGS_APP)


def base_dir() -> str:
    """Retourne le dossier racine des ressources de l'application (_MEIPASS si PyInstaller)."""
    if hasattr(sys, "_MEIPASS"):
        return getattr(sys, "_MEIPASS")
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def app_executable_dir() -> str:
    """Retourne le dossier réel de l'exécutable ou du script principal."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_user_data_dir() -> str:
    """
    Retourne le dossier des données utilisateur persistantes.
    Si un fichier 'portable.txt' est présent dans le dossier de l'exécutable,
    utilise un sous-dossier 'data' local (Mode Portable).
    Sinon, utilise %APPDATA%/DofusOrganizer (Standard Windows).
    """
    exe_dir = app_executable_dir()
    if os.path.isfile(os.path.join(exe_dir, "portable.txt")):
        path = os.path.join(exe_dir, "data")
    else:
        appdata = os.environ.get("APPDATA")
        if appdata:
            path = os.path.join(appdata, SETTINGS_APP)
        else:
            path = os.path.join(os.path.expanduser("~"), f".{SETTINGS_APP.lower()}")
    os.makedirs(path, exist_ok=True)
    return path


def resource_path(rel: str) -> str:
    """Retourne le chemin absolu vers une ressource relative à la racine du projet."""
    return os.path.normpath(os.path.join(base_dir(), rel))



# --- Thèmes QSS ---

THEMES = {
    "dark": "themes/gamer_dark.qss",
    "light": "themes/gamer_light.qss",
    "gold": "themes/gamer_gold.qss",
    "red": "themes/gamer_red.qss",
    "green": "themes/gamer_green.qss",
    "blue": "themes/gamer_blue.qss",
}


def theme_path(key_or_path: str = "dark") -> str:
    """
    Retourne le chemin absolu vers le fichier QSS demandé.
    Accepte une clé ('dark' / 'light') ou un chemin de fichier direct.
    """
    if not key_or_path:
        key_or_path = "dark"

    # Si c'est déjà un chemin existant
    cand = key_or_path
    if not os.path.isabs(cand):
        cand = resource_path(cand)
    if os.path.isfile(cand):
        return cand

    # Sinon traitement par clé
    key = str(key_or_path).lower().strip()
    rel = THEMES.get(key, THEMES["dark"])
    return resource_path(rel)


def apply_theme_to_app(app: Optional[QtWidgets.QApplication] = None, key_or_path: str = "dark") -> None:
    """Charge et applique la feuille de style QSS sur l'instance QApplication."""
    target_app = app or QtWidgets.QApplication.instance()
    if not target_app:
        return

    path = theme_path(key_or_path)
    try:
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
                qss = f.read()
            target_app.setStyleSheet(qss)
            return
    except Exception as e:
        print(f"[theme] Erreur chargement QSS '{path}': {e}")

    # Fallback minimal sombre
    target_app.setStyleSheet("QWidget { background:#0E0F12; color:#F5F7FA; font-family:'Segoe UI',sans-serif; }")


def apply_theme_from_settings(app: Optional[QtWidgets.QApplication] = None) -> None:
    """Lit le thème enregistré dans QSettings et l'applique à l'application."""
    s = get_app_settings()
    key = str(s.value("ui/theme", "dark")).lower()
    apply_theme_to_app(app, key)


# --- Icônes & Classes Dofus ---

ASSET_DEFAULT_ICON = "assets/icon/account.svg"

CLASS_ICON_MAP = {
    "cra": "assets/icon/Cra-3.0.png",
    "sram": "assets/icon/Sram-3.0.png",
    "ecaflip": "assets/icon/Ecaflip-3.0.png",
    "eliotrope": "assets/icon/Eliotrope-3.0.png",
    "eniripsa": "assets/icon/Eniripsa-3.0.png",
    "enutrof": "assets/icon/Enutrof-3.0.png",
    "feca": "assets/icon/Feca-3.0.png",
    "forgelance": "assets/icon/Forgelance-3.0.png",
    "huppermage": "assets/icon/Huppermage-3.0.png",
    "iop": "assets/icon/Iop-3.0.png",
    "osamodas": "assets/icon/Osamodas-3.0.png",
    "ouginak": "assets/icon/Ouginak-3.0.png",
    "pandawa": "assets/icon/Pandawa-3.0.png",
    "roublard": "assets/icon/Roublard-3.0.png",
    "sacrieur": "assets/icon/Sacrieur-3.0.png",
    "sadida": "assets/icon/Sadida-3.0.png",
    "steamer": "assets/icon/Steamer-3.0.png",
    "xelor": "assets/icon/Xelor-3.0.png",
    "zobal": "assets/icon/Zobal-3.0.png",
}


def load_icon(name: str) -> QtGui.QIcon:
    """Charge un QIcon depuis assets/icon/<name>."""
    rel = os.path.join("assets", "icon", name)
    path = resource_path(rel)
    if os.path.isfile(path):
        return QtGui.QIcon(path)
    return QtGui.QIcon()


def icon_for_class(classe: str) -> str:
    """
    Retourne le chemin absolu vers l'icône de classe (compatible Dofus 3.0 PNG).
    Fallback automatique sur l'icône par défaut si non trouvée.
    """
    key = str(classe or "").strip().lower()
    rel = CLASS_ICON_MAP.get(key, ASSET_DEFAULT_ICON)
    path = resource_path(rel)

    if os.path.isfile(path):
        return path

    # Essayer le fallback 2.0 (sans "-3.0")
    rel_alt = f"assets/icon/{classe.capitalize()}.png"
    path_alt = resource_path(rel_alt)
    if os.path.isfile(path_alt):
        return path_alt

    # Fallback icône générique
    fallback = resource_path(ASSET_DEFAULT_ICON)
    return fallback if os.path.isfile(fallback) else ""
