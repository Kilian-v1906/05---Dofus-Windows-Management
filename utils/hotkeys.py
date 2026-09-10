"""
utils/hotkeys.py
Normalisation, formattage et enregistrement sécurisé des raccourcis clavier globaux.
"""

from typing import Optional, Callable
import keyboard
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent, QKeySequence

MODIFIER_ORDER = ("ctrl", "alt", "shift", "windows")
MODIFIER_DISPLAY = {
    "ctrl": "Ctrl",
    "alt": "Alt",
    "shift": "Shift",
    "windows": "Win",
}

QT_SPECIAL_KEYS = {
    Qt.Key_Tab: "tab",
    Qt.Key_Backtab: "tab",
    Qt.Key_Space: "space",
    Qt.Key_Return: "enter",
    Qt.Key_Enter: "enter",
    Qt.Key_Backspace: "backspace",
    Qt.Key_Delete: "delete",
    Qt.Key_Insert: "insert",
    Qt.Key_Home: "home",
    Qt.Key_End: "end",
    Qt.Key_PageUp: "page up",
    Qt.Key_PageDown: "page down",
    Qt.Key_Up: "up",
    Qt.Key_Down: "down",
    Qt.Key_Left: "left",
    Qt.Key_Right: "right",
    Qt.Key_Escape: "esc",
    Qt.Key_CapsLock: "caps lock",
    Qt.Key_NumLock: "num lock",
    Qt.Key_ScrollLock: "scroll lock",
    Qt.Key_Print: "print screen",
    Qt.Key_Pause: "pause",
}

for _i in range(1, 25):
    _key_attr = getattr(Qt, f"Key_F{_i}", None)
    if _key_attr is not None:
        QT_SPECIAL_KEYS[_key_attr] = f"f{_i}"


def qt_key_event_to_hotkey_string(event: QKeyEvent) -> str:
    """
    Convertit un QKeyEvent Qt en chaîne normalisée compatible avec la lib keyboard.
    """
    key = event.key()
    if key in (Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Meta, Qt.Key_AltGr):
        return ""

    mods = []
    mod_flags = event.modifiers()
    if mod_flags & Qt.ControlModifier:
        mods.append("ctrl")
    if mod_flags & Qt.AltModifier:
        mods.append("alt")
    if mod_flags & Qt.ShiftModifier:
        mods.append("shift")
    if mod_flags & Qt.MetaModifier:
        mods.append("windows")

    key_str = ""
    if key in QT_SPECIAL_KEYS:
        key_str = QT_SPECIAL_KEYS[key]
    else:
        text = event.text()
        if text and len(text) == 1 and text.isprintable():
            key_str = text.lower()
        else:
            seq = QKeySequence(key).toString().lower()
            if seq:
                key_str = seq

    if not key_str:
        return ""

    if mods:
        clean_mods = [m for m in mods if m != key_str]
        if clean_mods:
            return "+".join(clean_mods + [key_str])
    return key_str



def normalize_hotkey_string(combo: str) -> str:
    """
    Normalise une combinaison de touches en une chaîne standardisée en minuscules
    compatible avec la bibliothèque keyboard (ex: 'ctrl+alt+tab', 'f1', 'tab').
    """
    if not combo or not combo.strip():
        return ""

    s = combo.strip().lower()
    # Remplacements de séparateurs courants
    for sep in (",", ";", "|"):
        s = s.replace(sep, "+")
    s = s.replace("++", "+").replace(" + ", "+").replace("+ ", "+").replace(" +", "+")
    s = s.strip("+ ").strip()

    # Découpage des morceaux
    raw_parts = [p.strip() for p in s.replace("+", " ").split() if p.strip()]

    mods = set()
    keys = []

    i = 0
    while i < len(raw_parts):
        p = raw_parts[i]

        # Gestion des modificateurs gauche / droite (ex: "left ctrl", "right alt")
        if p in ("left", "right") and i + 1 < len(raw_parts):
            next_p = raw_parts[i + 1]
            merged = f"{p} {next_p}"
            if merged in ("right alt", "left alt", "alt gr", "alt-gr", "altgr"):
                mods.add("alt")
                i += 2
                continue
            if merged in ("left ctrl", "right ctrl"):
                mods.add("ctrl")
                i += 2
                continue
            if merged in ("left shift", "right shift"):
                mods.add("shift")
                i += 2
                continue
            if merged in ("left windows", "right windows", "left win", "right win"):
                mods.add("windows")
                i += 2
                continue

        if p in ("altgr", "alt-gr", "alt_gr", "alt gr"):
            mods.update(("ctrl", "alt"))
        elif p in ("ctrl", "control"):
            mods.add("ctrl")
        elif p == "alt":
            mods.add("alt")
        elif p == "shift":
            mods.add("shift")
        elif p in ("windows", "win", "super", "cmd"):
            mods.add("windows")
        elif p in ("left", "right"):
            # Mot orphelin, on ignore
            pass
        else:
            # Nettoyer les doublons de modificateurs résiduels
            if p not in ("ctrl", "alt", "shift", "windows", "win", "control"):
                keys.append(p)
        i += 1

    ordered_mods = [m for m in MODIFIER_ORDER if m in mods]
    main_key = keys[-1] if keys else ""

    if ordered_mods and main_key:
        return "+".join(ordered_mods + [main_key])
    elif main_key:
        return main_key
    elif ordered_mods:
        return "+".join(ordered_mods)
    return ""


def format_hotkey_display(combo: str) -> str:
    """
    Formate un raccourci pour un affichage propre dans l'interface utilisateur.
    Exemples :
      - 'ctrl+tab' -> 'Ctrl + Tab'
      - 'shift+tab' -> 'Shift + Tab'
      - 'f1' -> 'F1'
      - 'ctrl+alt+a' -> 'Ctrl + Alt + A'
    """
    normalized = normalize_hotkey_string(combo)
    if not normalized:
        return ""

    parts = normalized.split("+")
    display_parts = []
    for p in parts:
        if p in MODIFIER_DISPLAY:
            display_parts.append(MODIFIER_DISPLAY[p])
        elif p.startswith("f") and p[1:].isdigit():
            display_parts.append(p.upper())
        elif len(p) == 1:
            display_parts.append(p.upper())
        else:
            display_parts.append(p.capitalize())

    return " + ".join(display_parts)


def clean_hotkey(hk: str) -> str:
    """Alias rétro-compatible pour normaliser une chaîne."""
    return normalize_hotkey_string(hk)


def register_hotkey_safe(
    hotkey_raw: str,
    callback: Callable[[], None],
    suppress: bool = False
) -> Optional[int]:
    """
    Enregistre un raccourci clavier global de façon sécurisée.
    Par défaut suppress=False pour ne pas bloquer les touches du clavier
    ni altérer le fonctionnement des touches de la souris.
    """
    hk = normalize_hotkey_string(hotkey_raw)
    if not hk:
        return None

    try:
        return keyboard.add_hotkey(hk, callback, suppress=suppress)
    except Exception as e:
        if suppress:
            try:
                return keyboard.add_hotkey(hk, callback, suppress=False)
            except Exception as e2:
                print(f"[hotkeys] Échec enregistrement hotkey '{hk}': {e2}")
        else:
            print(f"[hotkeys] Échec enregistrement hotkey '{hk}': {e}")
    return None


def unregister_hotkey_safe(hook_id: Optional[int]) -> None:
    """Retire un hook clavier global enregistré."""
    if hook_id is None:
        return
    try:
        keyboard.remove_hotkey(hook_id)
    except Exception:
        pass
