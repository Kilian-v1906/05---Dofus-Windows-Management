import sys
import time
import threading
import os

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QListWidget, QListWidgetItem, QComboBox, QCheckBox, QMessageBox,
    QGraphicsDropShadowEffect, QMenu, QAbstractItemView, QDialog, QSpinBox
)
from PySide6.QtGui import QPixmap, QColor
from PySide6.QtCore import Qt, QSize, Signal, QObject, QTimer, QPoint, QSettings

import win32gui
import win32con
import keyboard
import ctypes
import win32process

from core.window_manager import get_dofus_windows
from core.profiles import (
    get_profiles_list, load_profile, save_profile
)

THEMES = {
    "dark":  "themes/gamer_dark.qss",
    "light": "themes/gamer_light.qss",  # optionnel
}

# ========= MINI MODE METRICS (toutes les tailles ici) =========
MINI_H          = 76     # hauteur totale du mini (fenêtre, défault 82px)
MINI_CARD_W     = 120    # largeur d'une carte (Défault 150px, réduit pour mini)
MINI_ICON       = 20     # taille de l'icône de classe (px, défault 36px)
MINI_SPACING    = 6      # spacing entre cartes (défault 8px)
LEFT_BAR_W      = 24     # poignée ⋮ + marge (défault 24px)
RIGHT_PANEL_W   = 150    # panneau texte + toggle + croix
ROOT_PAD        = 6      # padding de #miniRoot (QSS: padding: 6px)

# Dérivées
MINI_INNER_H    = MINI_H - (ROOT_PAD * 2)      # hauteur utile à l'intérieur du verre
MINI_CARD_H     = 60 #MINI_INNER_H                 # hauteur d'une carte (ajuste si tu veux un peu moins)


def _resolve_theme_path(key_or_path: str) -> str:
    if not key_or_path:
        key_or_path = "dark"
    base = os.path.dirname(os.path.abspath(__file__))

    # 1) Si c'est un fichier existant → OK
    candidate = key_or_path if os.path.isabs(key_or_path) else os.path.join(base, key_or_path)
    if os.path.isfile(candidate):
        return candidate

    # 2) Sinon traiter comme "clé"
    key = (key_or_path or "").lower()
    rel = THEMES.get(key, THEMES["dark"])
    return os.path.join(base, rel)

def apply_theme_to_app(app: QtWidgets.QApplication, key_or_path: str = "dark"):
    """Charge un QSS depuis une clé ('dark'/'light') OU un chemin. Log détaillé + fallback"""
    print(f"[theme] apply_theme_to_app called with: {key_or_path}")
    path = _resolve_theme_path(key_or_path)
    try:
        with open(path, "r", encoding="utf-8") as f:
            qss = f.read()
        app.setStyleSheet(qss)
    except Exception as e:
        print(f"[theme] Failed to load QSS '{path}': {e}")
        fallback = """
            QWidget { background: #0E0F12; color: #F5F7FA; }
            #miniRoot { background: rgba(255,0,0,0.35); border: 2px solid #ff0066; border-radius: 16px; }
        """
        app.setStyleSheet(fallback)
        print("[theme] Fallback QSS applied.")

def apply_theme_key(app: QtWidgets.QApplication, key: str):
    """Applique le thème à partir d'une clé ('dark'|'light'), avec fallback."""
    path = THEMES.get((key or "").lower(), THEMES["dark"])
    apply_theme_to_app(app, path)


def load_icon(name: str) -> QtGui.QIcon:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    p1 = os.path.join("assets", "icon", name)
    p2 = os.path.join(base_dir, "assets", "icon", name)
    path = p1 if os.path.exists(p1) else (p2 if os.path.exists(p2) else "")
    return QtGui.QIcon(path) if path else QtGui.QIcon()


# --------- Assets & Classes icons ---------
ASSET_ICON = "assets/icon/account.svg"
CLASS_ICON_MAP = {
    "Cra":  "assets/Icon/Cra-3.0.png",
    "Sram": "assets/Icon/Sram-3.0.png",
    "Ecaflip": "assets/Icon/Ecaflip-3.0.png",
    "Eliotrope": "assets/Icon/Eliotrope-3.0.png",
    "Eniripsa": "assets/Icon/Eniripsa-3.0.png",
    "Enutrof": "assets/Icon/Enutrof-3.0.png",
    "Feca": "assets/Icon/Feca-3.0.png",
    "Forgelance": "assets/Icon/Forgelance-3.0.png",
    "Huppermage": "assets/Icon/Huppermage-3.0.png",
    "Iop": "assets/Icon/Iop-3.0.png",
    "Osamodas": "assets/Icon/Osamodas-3.0.png",
    "Ouginak": "assets/Icon/Ouginak-3.0.png",
    "Pandawa": "assets/Icon/Pandawa-3.0.png",
    "Roublard": "assets/Icon/Roublard-3.0.png",
    "Sacrieur": "assets/Icon/Sacrieur-3.0.png",
    "Sadida": "assets/Icon/Sadida-3.0.png",
    "Steamer": "assets/Icon/Steamer-3.0.png",
    "Xelor": "assets/Icon/Xelor-3.0.png",
    "Zobal": "assets/Icon/Zobal-3.0.png",
}

def load_icon(name: str) -> QtGui.QIcon:
    """
    Charge un QIcon depuis assets/icon/<name>.
    Fallback: retourne un QIcon vide si non trouvé.
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    p1 = os.path.join("assets", "icon", name)
    p2 = os.path.join(base_dir, "assets", "icon", name)
    path = p1 if os.path.exists(p1) else (p2 if os.path.exists(p2) else "")
    return QtGui.QIcon(path) if path else QtGui.QIcon()


def normalize_hotkey_string(combo: str) -> str:

    if not combo:
        return combo

    s = combo.strip().lower()
    # uniformiser séparateurs
    s = s.replace(" + ", "+").replace("++", "+").replace("  ", " ")
    s = s.replace(",", "+")  # au cas où

    # Tokenize grossièrement
    parts = [p for p in s.replace("+", " + ").split() if p != "+"]

    mods = set()
    keys = []

    i = 0
    while i < len(parts):
        p = parts[i]

        # Coller "right alt" / "left alt" etc.
        if p in ("left", "right") and i + 1 < len(parts):
            merged = f"{p} {parts[i+1]}"
            if merged == "right alt":
                # Right Alt -> alt (pas 'right alt')
                mods.add("alt")
                i += 2
                continue
            elif merged == "left alt":
                mods.add("alt"); i += 2; continue
            elif merged in ("left ctrl", "right ctrl"):
                mods.add("ctrl"); i += 2; continue
            elif merged in ("left shift", "right shift"):
                mods.add("shift"); i += 2; continue
            elif merged in ("left windows", "right windows"):
                mods.add("windows"); i += 2; continue

        # AltGr variantes -> ctrl+alt
        if p in ("altgr", "alt-gr", "alt_gr", "alt gr"):
            mods.update(("ctrl", "alt"))
        elif p in ("ctrl", "control"):
            mods.add("ctrl")
        elif p in ("alt",):
            mods.add("alt")
        elif p in ("shift",):
            mods.add("shift")
        elif p in ("windows", "win", "super", "cmd"):
            mods.add("windows")
        else:
            # touche principale (on garde la dernière si doublons)
            keys.append(p)
        i += 1

    # Si la "touche" contient encore 'right alt', corriger
    keys = [("alt" if k == "right alt" else k) for k in keys]

    # Retirer les touches qui sont en fait des modifs résiduelles
    keys = [k for k in keys if k not in ("ctrl", "control", "alt", "shift", "windows", "win", "super", "cmd", "right alt")]

    # Ordre des modifs stable
    ordered_mods = [m for m in ("ctrl", "alt", "shift", "windows") if m in mods]

    # Ne garder qu'une touche principale (éviter séquences)
    key = keys[-1] if keys else ""

    if ordered_mods and key:
        return "+".join(ordered_mods + [key])
    elif key:
        return key
    elif ordered_mods:
        # hotkey uniquement modificateurs (peu utile) -> garder quand même
        return "+".join(ordered_mods)
    return ""

def _sanitize_hotkey_for_keyboard(hk: str) -> str:
    if not hk:
        return ""

    s = hk.strip().lower()
    # uniformise séparateurs
    for ch in [",", ";"]:
        s = s.replace(ch, "+")
    s = s.replace(" + ", "+").replace("++", "+").replace("  ", " ")
    s = s.replace(" +", "+").replace("+ ", "+")
    s = s.strip("+ ").strip()

    # éclate en tokens
    parts = [p for p in s.replace("+", " + ").split() if p != "+"]

    mods = set()
    keys = []

    i = 0
    while i < len(parts):
        p = parts[i]

        # Coller 'right alt' / 'left alt', etc.
        if p in ("left", "right") and i + 1 < len(parts):
            merged = f"{p} {parts[i+1]}"
            if merged == "right alt":
                mods.add("alt")
                i += 2
                continue
            if merged == "left alt":
                mods.add("alt")
                i += 2
                continue
            if merged in ("left ctrl", "right ctrl"):
                mods.add("ctrl"); i += 2; continue
            if merged in ("left shift", "right shift"):
                mods.add("shift"); i += 2; continue
            if merged in ("left windows", "right windows"):
                mods.add("windows"); i += 2; continue

        # Variantes AltGr -> ctrl+alt
        if p in ("altgr", "alt-gr", "alt_gr", "alt gr"):
            mods.update(("ctrl", "alt"))
        elif p in ("ctrl", "control"):
            mods.add("ctrl")
        elif p in ("alt",):
            mods.add("alt")
        elif p in ("shift",):
            mods.add("shift")
        elif p in ("windows", "win", "super", "cmd"):
            mods.add("windows")
        elif p in ("right", "left"):
            pass  # déjà géré ci-dessus si pertinent
        else:
            keys.append(p)
        i += 1

    # nettoyer les touches principales résiduelles
    bad = {"ctrl", "control", "alt", "shift", "windows", "win", "super", "cmd", "right alt", "left alt"}
    keys = [("alt" if k == "right alt" else k) for k in keys if k not in bad]

    # ordonner mods
    ordered_mods = [m for m in ("ctrl", "alt", "shift", "windows") if m in mods]

    # une seule touche principale max (la dernière pressée)
    key = keys[-1] if keys else ""

    if ordered_mods and key:
        return "+".join(ordered_mods + [key])
    elif key:
        return key
    elif ordered_mods:
        return "+".join(ordered_mods)
    return ""

def _clean_hotkey(hk: str) -> str:
    """
    Nettoyage minimal pour éviter l'erreur 'Key ' right alt'...':
    - trim, lowercase
    - enlève l'espace parasite devant 'right alt'
    - remplace 'right alt' par 'alt' (keyboard ne connaît pas 'right alt')
    - compresse ' + ' -> '+'
    """
    if not hk:
        return ""
    s = hk.strip().lower()
    s = s.replace(" right alt", " right-alt")  # évite le token ' right'
    s = s.replace("right-alt", "alt")
    s = s.replace(" + ", "+").replace("++", "+").strip("+ ").strip()
    return s


def _safe_add_hotkey(hk_raw: str, callback):
    """
    Normalise puis enregistre un hotkey via 'keyboard.add_hotkey'.
    Lève ValueError si la chaîne est vide après normalisation.
    Retourne l'identifiant du hook.
    """
    hk = _sanitize_hotkey_for_keyboard(hk_raw)
    if not hk:
        raise ValueError("Hotkey vide ou invalide après normalisation.")

    # Defensive: éviter 'right alt' résiduel
    if "right alt" in hk:
        hk = hk.replace("right alt", "alt")

    return keyboard.add_hotkey(hk, callback, suppress=True)


def icon_for_class(classe: str) -> str:
    rel = CLASS_ICON_MAP.get((classe or "").strip(), ASSET_ICON)

    # 1) Essai tel quel (cwd)
    if os.path.exists(rel):
        return rel

    # 2) Essai relatif au dossier de ce fichier (main.py)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    alt = os.path.join(base_dir, rel)
    if os.path.exists(alt):
        return alt

    # 3) Dernier recours : icône par défaut, résolue pareil
    if os.path.exists(ASSET_ICON):
        return ASSET_ICON
    alt_def = os.path.join(base_dir, ASSET_ICON)
    return alt_def if os.path.exists(alt_def) else ASSET_ICON


def force_foreground(hwnd: int):
    """Force proprement le focus sur hwnd (contourne les protections Windows)."""
    try:
        user32 = ctypes.windll.user32
        fg = win32gui.GetForegroundWindow()
        tid_fore = win32process.GetWindowThreadProcessId(fg)[0] if fg else 0
        tid_tgt  = win32process.GetWindowThreadProcessId(hwnd)[0]

        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        else:
            win32gui.ShowWindow(hwnd, win32con.SW_SHOW)

        if tid_fore and tid_fore != tid_tgt:
            user32.AttachThreadInput(tid_fore, tid_tgt, True)

        user32.SetForegroundWindow(hwnd)
        user32.BringWindowToTop(hwnd)
        user32.SetFocus(hwnd)

        if tid_fore and tid_fore != tid_tgt:
            user32.AttachThreadInput(tid_fore, tid_tgt, False)
    except Exception:
        # fallback "Alt" hack si nécessaire
        try:
            import keyboard
            keyboard.send('alt')
            win32gui.SetForegroundWindow(hwnd)
        except Exception:
            pass


# --------- THEME (dark / light) ---------
def app_stylesheet(theme: str) -> str:
    if theme == "light":
        return """
        QWidget { background:#f4f6f8; color:#1b1d21; font-family:'Segoe UI'; }
        QLabel { color:#1b1d21; }
        QPushButton { background: rgba(0,0,0,0.06); border:1px solid rgba(0,0,0,0.15); border-radius:8px; padding:6px 10px; color:#1b1d21; }
        QPushButton:hover { background: rgba(0,0,0,0.12); }
        QComboBox { background: #ffffff; border:1px solid rgba(0,0,0,0.15); border-radius:6px; padding:4px; color:#1b1d21; }
        QListWidget { background: transparent; }
        """
    # dark (default)
    return """
    QWidget { background:#131416; color:#ffffff; font-family:'Segoe UI'; }
    QPushButton { background: rgba(255,255,255,0.08); border:1px solid rgba(255,255,255,0.15); border-radius:8px; padding:6px 10px; }
    QPushButton:hover { background: rgba(255,255,255,0.18); }
    QComboBox { background: rgba(255,255,255,0.10); border-radius:6px; padding:4px; color:white; }
    QListWidget { background: transparent; }
    """


class MiniCardItem(QWidget):
    """Carte compacte du mini-mode (rangées horizontalement)."""
    toggled = Signal(int, bool)       # handle, enabled
    request_focus = Signal(int)       # handle (clic carte → focus)

    def __init__(self, index: int, pseudo: str, classe: str, handle: int, enabled: bool):
        super().__init__()
        self.handle = handle
        self.pseudo = pseudo
        self.classe = classe

        card = QtWidgets.QFrame(objectName="miniCard")
        card.setStyleSheet("")  # QSS gère le style

        sh = QGraphicsDropShadowEffect(card)
        sh.setBlurRadius(10)
        sh.setOffset(0, 2)
        sh.setColor(QColor(0, 0, 0, 100))
        card.setGraphicsEffect(sh)

        # Layout très compact
        root = QHBoxLayout(card)
        root.setContentsMargins(6, 2, 6, 2)   # moins de marge
        root.setSpacing(4)

        # --- Colonne 1 : index (peu de marge à gauche)
        col_idx = QVBoxLayout()
        col_idx.setContentsMargins(0, 0, 0, 0)
        col_idx.setSpacing(0)
        self._idx_label = QLabel(f"#{index+1}", objectName="miniIndex")
        col_idx.addStretch()
        col_idx.addWidget(self._idx_label, 0, Qt.AlignHCenter)
        col_idx.addStretch()
        root.addLayout(col_idx, 0)

        # --- Colonne 2 : icône classe
        col_icon = QVBoxLayout()
        col_icon.setContentsMargins(0, 0, 0, 0)
        col_icon.setSpacing(0)
        icon = QLabel()
        pm = QPixmap(icon_for_class(classe))
        if not pm.isNull():
            pm = pm.scaled(MINI_ICON, MINI_ICON, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            icon.setPixmap(pm)
        icon.setFixedSize(MINI_ICON + 2, MINI_ICON + 2)
        icon.setAlignment(Qt.AlignCenter)
        col_icon.addStretch()
        col_icon.addWidget(icon, 0, Qt.AlignHCenter)
        col_icon.addStretch()
        root.addLayout(col_icon, 0)

        # --- Colonne 3 : toggle + nom + classe
        col_text = QVBoxLayout()
        col_text.setContentsMargins(0, 0, 0, 0)
        col_text.setSpacing(1)

        # Toggle plus petit (le QSS fait le look, on se contente du widget)
        self.chk = QCheckBox()
        self.chk.setChecked(bool(enabled))
        self.chk.stateChanged.connect(lambda s: self.toggled.emit(self.handle, bool(s)))

        row_toggle = QHBoxLayout()
        row_toggle.setContentsMargins(0, 0, 0, 0)
        row_toggle.setSpacing(0)
        row_toggle.addStretch()
        row_toggle.addWidget(self.chk, 0, Qt.AlignRight)

        name = QLabel(pseudo)
        name.setStyleSheet("font-weight:600; font-size:11px;")  # plus petit
        clas = QLabel(classe)
        clas.setProperty("muted", True)
        clas.setStyleSheet("font-size:10px;")                    # plus petit

        col_text.addLayout(row_toggle)
        col_text.addWidget(name, 0, Qt.AlignLeft)
        col_text.addWidget(clas, 0, Qt.AlignLeft)
        root.addLayout(col_text, 1)

        # Wrapper final
        wrap = QHBoxLayout(self)
        wrap.setContentsMargins(0, 0, 0, 0)
        wrap.addWidget(card)

        # Taille compacte
        card.setFixedHeight(MINI_CARD_H)
        self.setFixedSize(MINI_CARD_W, MINI_CARD_H)

        # Clic carte → focus (sauf clic sur le toggle)
        def _clicked(e: QtGui.QMouseEvent):
            if hasattr(e, "position"):
                pos = e.position().toPoint()
            else:
                pos = e.pos()
            w = card.childAt(pos)
            if w is None or not isinstance(w, QCheckBox):
                self.request_focus.emit(self.handle)

        card.mouseReleaseEvent = _clicked

    def set_index(self, i: int):
        self._idx_label.setText(f"#{i+1}")


class MiniModeWindow(QWidget):
    def __init__(self, parent_main: QWidget, windows: list[dict]):
        super().__init__(parent_main)
        self.main = parent_main
        self.windows = list(windows)[:8]  # max 8 cartes
        self._handles_set = {w.get("handle") for w in self.windows if w.get("handle") and w.get("enabled")}
        self.hide_outside_dofus = bool(self.main.settings.value("mini/hide_outside", True, bool))
        self.always_on_top = bool(self.main.settings.value("mini/always_on_top", False, bool))

        # Overlay frameless + transparent + toujours au-dessus
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.Tool
            | Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setWindowIcon(QtGui.QIcon("assets/icon/dwm.ico"))


        # Racine (sans marges)
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Conteneur "verre" stylé par QSS (#miniRoot)
        cont = QtWidgets.QFrame(objectName="miniRoot")
        # IMPORTANT : le padding visuel est géré par le QSS (#miniRoot { padding: ROOT_PAD px })
        # Ici, on fixe la hauteur "utile" pour éviter que le contenu pousse la fenêtre.
        cont.setFixedHeight(MINI_H - (ROOT_PAD * 2))
        cont.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)

        cv = QHBoxLayout(cont)
        cv.setContentsMargins(ROOT_PAD, ROOT_PAD, ROOT_PAD, ROOT_PAD)  # marge = ROOT_PAD
        cv.setSpacing(MINI_SPACING)

        # 1) Poignée gauche (⋮)
        self.drag = QLabel("⋮", objectName="miniDrag")
        self.drag.setCursor(Qt.OpenHandCursor)
        self.drag.installEventFilter(self)
        cv.addWidget(self.drag, 0, Qt.AlignLeft | Qt.AlignTop)

        # 2) Rangée horizontale des cartes
        self.cards_row = QHBoxLayout()
        self.cards_row.setContentsMargins(0, 0, 0, 0)
        self.cards_row.setSpacing(MINI_SPACING)
        cv.addLayout(self.cards_row, 1)

        # --- PANNEAU DE DROITE (unique) ---
        # Retirer toute version précédente (par sécurité si recréation)
        old = self.findChild(QWidget, "miniRightPanel")
        if old is not None:
            old.setParent(None)
            old.deleteLater()

        right_w = QWidget()
        right_w.setObjectName("miniRightPanel")
        right_w.setFixedWidth(RIGHT_PANEL_W)
        right_w.setFixedHeight(MINI_H - (ROOT_PAD * 2))
        right_w.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)

        right = QVBoxLayout(right_w)
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(4)

        # Label sur deux lignes, sans background (géré par QSS)
        lab = QLabel("Afficher seulement\nau-dessus de Dofus")
        lab.setWordWrap(True)
        lab.setProperty("muted", True)

        # Switch (QCheckBox) – taille gérée par QSS
        self.hide_chk = QCheckBox()
        self.hide_chk.setChecked(self.hide_outside_dofus)
        self.hide_chk.stateChanged.connect(self._on_hide_toggle)

        # Bouton croix à droite du label
        self.btn_close = QPushButton("✕")
        self.btn_close.setObjectName("miniCloseBare")
        self.btn_close.setFixedSize(20, 20)
        self.btn_close.clicked.connect(self._exit_to_main)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(4)
        top_row.addWidget(lab, 1)
        top_row.addWidget(self.btn_close, 0, Qt.AlignRight)

        right.addStretch()
        right.addLayout(top_row)
        right.addWidget(self.hide_chk, 0, Qt.AlignLeft)
        right.addStretch()

        cv.addWidget(right_w, 0)


        # Ajouter le conteneur verre à la racine
        root.addWidget(cont)

        # Contenu (cartes)
        self._populate_cards()

        # Timer topmost/hide (+ grâce de démarrage)
        self._opened_at = time.monotonic()
        self._drag_pos: QPoint | None = None

        # Taille & position
        self._auto_resize_and_center()

         # --- Timer de visibilité (masquer hors Dofus) ---
        self._vis_timer = QTimer(self)
        self._vis_timer.setInterval(400)  # 0.4s
        self._vis_timer.timeout.connect(self._visibility_tick)
        self._vis_timer.start()



    def _populate_cards(self):
        # nettoie les widgets existants
        while self.cards_row.count():
            it = self.cards_row.takeAt(0)
            w = it.widget()
            if w:
                w.deleteLater()
        self._card_widgets = []

        # ajoute les cartes MiniCardItem (jusqu'à 8)
        for i, w in enumerate(self.windows[:8]):
            card = MiniCardItem(
                index=i,
                pseudo=w.get("pseudo", ""),
                classe=w.get("classe", ""),
                handle=w.get("handle"),
                enabled=bool(w.get("enabled")),
            )
            card.toggled.connect(self._on_toggle_enabled)
            card.request_focus.connect(self._focus_handle)
            self.cards_row.addWidget(card)
            self._card_widgets.append(card)


    def _current_handles_order(self):
        order = []
        for card in self._card_widgets:
            h = getattr(card, "handle", None)
            if h:
                order.append(h)
        return order
    
    def _sync_back_to_main_from_mini(self):
        ordered = []
        for card in self._card_widgets:
            ordered.append({
                "pseudo": getattr(card, "pseudo", ""),   # si tu veux les stocker : ajoute self.pseudo à MiniCardItem
                "classe": getattr(card, "classe", ""),   # idem (voir note plus bas)
                "handle": getattr(card, "handle", None),
                "enabled": bool(card.chk.isChecked())
            })
        self.windows = ordered
        self._handles_set = {w.get("handle") for w in self.windows if w.get("handle") and w.get("enabled")}
        try:
            self.main.reorder_main_list_by_handles(self._current_handles_order())
        except Exception:
            pass
        self._auto_resize_and_center()

    def reorder_from_main(self, handles_order: list[int]):
        # Recrée l'ordre visuel selon la liste de handles
        handle_to_card = {getattr(c, "handle", None): c for c in self._card_widgets}
        new_cards = []
        for h in handles_order:
            c = handle_to_card.get(h)
            if c:
                new_cards.append(c)
        # Ajoute ceux non listés à la fin
        for c in self._card_widgets:
            if c not in new_cards:
                new_cards.append(c)

        # Ré-attache dans le layout
        while self.cards_row.count():
            self.cards_row.takeAt(0)
        for i, c in enumerate(new_cards):
            # mettre à jour le badge d'index
            c.set_index(i)
            self.cards_row.addWidget(c)

        self._card_widgets = new_cards
        self._auto_resize_and_center()

    def _auto_resize_and_center(self):
        n = max(1, len(self.windows[:8]))
        total_w = LEFT_BAR_W + (n * MINI_CARD_W + (n - 1) * MINI_SPACING) + RIGHT_PANEL_W + (ROOT_PAD * 2)
        total_h = MINI_H

        self.setMinimumSize(total_w, total_h)
        self.setMaximumSize(total_w, total_h)
        self.resize(total_w, total_h)

        try:
            scr = QtGui.QGuiApplication.primaryScreen().availableGeometry()
            x = scr.x() + (scr.width() - total_w) // 2
            y = scr.y() + 12
            self.move(x, y)
        except Exception:
            pass


    def eventFilter(self, obj, event):
        if obj is self.drag:
            et = event.type()

            if et == QtCore.QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                # Point de départ du drag (Qt6 → globalPosition())
                self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                self.drag.setCursor(Qt.ClosedHandCursor)
                return True

            elif et == QtCore.QEvent.MouseMove and self._drag_pos is not None and (event.buttons() & Qt.LeftButton):
                # Déplacement fluide
                self.move(event.globalPosition().toPoint() - self._drag_pos)
                return True

            elif et == QtCore.QEvent.MouseButtonRelease:
                self._drag_pos = None
                self.drag.setCursor(Qt.OpenHandCursor)
                return True

        # Laisser le reste des événements suivre le chemin normal
        return QWidget.eventFilter(self, obj, event)


    # ---------- actions ----------
    def _define_hotkey_from_card(self, handle: int, pseudo: str):
        try: self.main.define_hotkey_for_handle_from_mini(handle, pseudo)
        except Exception: pass

    def _on_toggle_enabled(self, handle: int, enabled: bool):
        try: self.main.set_focus_enabled_for_handle(handle, enabled)
        except Exception: pass
        if enabled: self._handles_set.add(handle)
        else: self._handles_set.discard(handle)

    def _focus_handle(self, hwnd: int):
        try:
            force_foreground(hwnd)
        except Exception:
            pass


    def _change_next_hotkey(self):
        dlg = HotkeyCaptureDialog("Raccourci global - Suivant", self)
        def _on_sel(hk: str):
            try:
                self.main.hotkey_next = hk
                self.main.lbl_next.setText(hk)
                self.key_label.setText(hk)
                self.main._register_global_next()
            except Exception: pass
        dlg.hotkey_selected.connect(_on_sel); dlg.exec()

    def _on_hide_toggle(self, s: int):
        # On ne fait que sauvegarder la préférence
        self.hide_outside_dofus = bool(s)
        try:
            self.main.settings.setValue("mini/hide_outside", self.hide_outside_dofus)
        except Exception:
            pass
        # pas de show/hide ici, le timer s’en charge



    def _update_topmost_state(self, force: bool = False):
        """Désactivé pour l'instant : on laisse Qt gérer le topmost via WindowStaysOnTopHint."""
        return



    def _exit_to_main(self):
        try:
            self.main.showNormal()
            self.main.raise_()
            self.main.activateWindow()
        except Exception:
            pass
        self.main._mini = None
        self.close()


    def set_next_hotkey_label(self, txt: str): self.key_label.setText(txt)


    def _on_toggle_enabled(self, handle: int, enabled: bool):
        try: self.main.set_focus_enabled_for_handle(handle, enabled)
        except Exception: pass
        if enabled: self._handles_set.add(handle)
        else: self._handles_set.discard(handle)

    def _on_double_click(self, item: QListWidgetItem):
        data = item.data(Qt.UserRole) or {}
        hwnd = data.get("handle")
        if hwnd:
            try:
                if win32gui.IsIconic(hwnd): win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                else: win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
                time.sleep(self.main.win32_delay_ms / 1000.0)
                win32gui.SetForegroundWindow(hwnd)
            except Exception: pass

    def _visibility_tick(self):
        """Masquer/afficher le mini en fonction de la fenêtre active, si l'option est cochée."""

        # Si l’option n’est pas active → toujours visible
        if not self.hide_outside_dofus:
            self.show()
            return

        # Ne rien faire pendant le drag (on te laisse tranquille)
        if self._drag_pos is not None:
            return

        # Fenêtre au premier plan
        try:
            fg = win32gui.GetForegroundWindow()
        except Exception:
            fg = None

        root = None
        if fg:
            try:
                root = win32gui.GetAncestor(fg, win32con.GA_ROOT)
            except Exception:
                root = fg

        hwnd_self = int(self.winId())
        dofus_handles = [w.get("handle") for w in self.windows if w.get("handle")]

        # Autorisé si : une fenêtre Dofus ou le mini lui-même a le focus
        is_allowed = (root == hwnd_self) or (root in dofus_handles)

        if is_allowed:
            self.show()
        else:
            self.hide()

# ========= Dialog Paramètres =========
class SettingsDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowIcon(QtGui.QIcon("assets/icon/dwm.ico"))
        self.setWindowTitle("Paramètres")
        self.setMinimumWidth(520)
        self.s = parent.settings

        v = QVBoxLayout(self)

        self.chk_always_on_top = QCheckBox("Mini-mode toujours visible (ignorer le focus Dofus)")
        self.chk_hide_outside = QCheckBox("Masquer le mini-mode quand Dofus n’est pas actif")

        self.spin_delay = QSpinBox()
        self.spin_delay.setRange(0, 150)
        self.spin_delay.setSuffix(" ms")

        info = QLabel(
            "Délai Win32 : temps d’attente entre la restauration et la mise au premier plan.\n"
            "Augmente-le (20–60 ms) si le focus saute ou se perd."
        )
        info.setStyleSheet("font-size:11px; opacity:0.8;")

        self.combo_theme = QComboBox()
        self.combo_theme.addItems(["Sombre", "Clair"])

        # Layout
        v.addWidget(self.chk_always_on_top)
        v.addWidget(self.chk_hide_outside)

        row = QHBoxLayout()
        row.addWidget(QLabel("Délai Win32:"))
        row.addWidget(self.spin_delay)
        v.addLayout(row)
        v.addWidget(info)

        row3 = QHBoxLayout()
        row3.addWidget(QLabel("Thème:"))
        row3.addWidget(self.combo_theme)
        v.addLayout(row3)

        btns = QHBoxLayout()
        bsave = QPushButton("Enregistrer"); bsave.clicked.connect(self.accept)
        bcancel = QPushButton("Annuler"); bcancel.clicked.connect(self.reject)
        btns.addStretch(); btns.addWidget(bcancel); btns.addWidget(bsave)
        v.addLayout(btns)

        self._load()

    def _load(self):
        self.chk_always_on_top.setChecked(self.s.value("mini/always_on_top", False, bool))
        self.chk_hide_outside.setChecked(self.s.value("mini/hide_outside", True, bool))
        self.spin_delay.setValue(int(self.s.value("win32/delay_ms", 20)))
        theme = self.s.value("ui/theme", "dark")
        self.combo_theme.setCurrentIndex(1 if theme == "light" else 0)

    def accept(self):
        self.s.setValue("mini/always_on_top", self.chk_always_on_top.isChecked())
        self.s.setValue("mini/hide_outside", self.chk_hide_outside.isChecked())
        self.s.setValue("win32/delay_ms", self.spin_delay.value())
        self.s.setValue("ui/theme", "light" if self.combo_theme.currentIndex() == 1 else "dark")
        super().accept()

class ProfileWinItemWidget(QWidget):
    """
    Ligne d’un compte dans 'Gestion des profils':
    - switch (enabled)
    - pseudo
    - classe
    - index #n (badge)
    """
    toggled = Signal(bool)

    def __init__(self, index: int, pseudo: str, classe: str, enabled: bool = True, parent: QWidget | None = None):
        super().__init__(parent)
        self.pseudo = pseudo
        self.classe = classe
        self.enabled = bool(enabled)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(8)

        self.chk = QCheckBox()
        self.chk.setChecked(self.enabled)
        self.chk.stateChanged.connect(lambda s: self.toggled.emit(bool(s)))

        name_box = QWidget()
        v = QVBoxLayout(name_box)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(2)
        self.lbl_name = QLabel(self.pseudo)
        self.lbl_name.setStyleSheet("font-size:14px; font-weight:600;")
        self.lbl_class = QLabel(self.classe)
        self.lbl_class.setProperty("muted", True)
        v.addWidget(self.lbl_name)
        v.addWidget(self.lbl_class)

        self.idx = QLabel(f"#{index+1}")
        self.idx.setObjectName("indexBadge")

        lay.addWidget(self.chk)
        lay.addWidget(name_box, 1)
        lay.addStretch()
        lay.addWidget(self.idx)

    def set_index(self, i: int):
        self.idx.setText(f"#{i+1}")

class ProfilesManagerDialog(QtWidgets.QDialog):
    def __init__(self, main: QWidget):
        super().__init__(main)
        self.main = main
        self.setWindowIcon(QtGui.QIcon("assets/icon/dwm.ico"))
        self.setWindowTitle("Gestion des profils")
        self.setModal(True)
        self.setMinimumSize(720, 480)

        self.profile_next_hotkey: str | None = None  # hotkey 'Suivant' du profil

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(10)

        # Barre d’actions top
        actions = QHBoxLayout()
        self.btn_new_from_open = QPushButton("Nouveau depuis fenêtres ouvertes")
        self.btn_rename = QPushButton("Renommer")
        self.btn_delete = QPushButton("Supprimer")
        self.btn_toggle_main = QPushButton("Basculer 'Profil principal'")
        actions.addWidget(self.btn_new_from_open)
        actions.addWidget(self.btn_rename)
        actions.addWidget(self.btn_delete)
        actions.addStretch()
        actions.addWidget(self.btn_toggle_main)
        root.addLayout(actions)

        # Panneaux gauche/droite
        body = QHBoxLayout()
        body.setSpacing(10)

        left_panel = QtWidgets.QFrame()
        left_panel.setObjectName("panelCard")
        left_l = QVBoxLayout(left_panel)
        left_l.setContentsMargins(10, 10, 10, 10)
        left_l.setSpacing(8)
        self.profiles_list = QListWidget()
        self._reload_profiles()
        left_l.addWidget(self.profiles_list)

        right_panel = QtWidgets.QFrame()
        right_panel.setObjectName("panelCard")
        right_l = QVBoxLayout(right_panel)
        right_l.setContentsMargins(10, 10, 10, 10)
        right_l.setSpacing(8)

        self.windows_list = QListWidget()
        self.windows_list.setDragDropMode(QAbstractItemView.InternalMove)
        self.windows_list.model().rowsMoved.connect(self._update_indexes_after_drag)
        right_l.addWidget(self.windows_list, 1)

        # Ligne hotkey du profil
        hk_row = QHBoxLayout()
        hk_row.addWidget(QLabel("Raccourci Suivant…"))
        self.btn_set_profile_next = QPushButton("Définir…")
        self.btn_set_profile_next.setFixedHeight(30)
        self.btn_set_profile_next.clicked.connect(self._capture_profile_next_hotkey)
        self.lbl_profile_next = QLabel("")
        self.lbl_profile_next.setObjectName("profileHotkeyBadge")
        self.lbl_profile_next.setMinimumWidth(56)
        hk_row.addWidget(self.btn_set_profile_next)
        hk_row.addWidget(self.lbl_profile_next)
        hk_row.addStretch()
        right_l.addLayout(hk_row)

        body.addWidget(left_panel, 1)
        body.addWidget(right_panel, 2)
        root.addLayout(body)

        # Bas
        bottom = QHBoxLayout()
        self.btn_delete_window = QPushButton("Supprimer entrée")
        bottom.addWidget(self.btn_delete_window)
        bottom.addStretch()
        self.btn_load_into_main = QPushButton("Charger dans l'appli")
        self.btn_save_profile = QPushButton("Enregistrer")
        bottom.addWidget(self.btn_load_into_main)
        bottom.addWidget(self.btn_save_profile)
        root.addLayout(bottom)

        # Connexions
        self.profiles_list.currentTextChanged.connect(self._on_profile_selected)
        self.btn_new_from_open.clicked.connect(self._new_from_open_windows)
        self.btn_rename.clicked.connect(self._rename_profile)
        self.btn_delete.clicked.connect(self._delete_profile)
        self.btn_delete_window.clicked.connect(self._delete_window_entry)
        self.btn_load_into_main.clicked.connect(self._load_into_main)
        self.btn_save_profile.clicked.connect(self._save_profile_content)
        self.btn_toggle_main.clicked.connect(self._toggle_main_profile)

    # ---------- Data & actions ----------
    def _reload_profiles(self):
        self.profiles_list.clear()
        try:
            for name in get_profiles_list():
                self.profiles_list.addItem(name)
        except Exception:
            pass

    def _on_profile_selected(self, name: str):
        self.windows_list.clear()
        self.profile_next_hotkey = None
        self.lbl_profile_next.setText("")
        if not name:
            return
        data = load_profile(name) or {}
        # hotkey du profil
        hk = (data.get("global_hotkeys") or {}).get("next")
        if hk:
            self.profile_next_hotkey = hk
            self.lbl_profile_next.setText(hk)

        # lignes comptes
        wins = data.get("windows", [])
        for i, w in enumerate(wins):
            pseudo = w.get("pseudo", "")
            classe = w.get("classe", "")
            enabled = bool(w.get("enabled", True))
            it = QListWidgetItem()
            it.setData(Qt.UserRole, {"pseudo": pseudo, "classe": classe, "enabled": enabled})
            it.setSizeHint(QSize(0, 58))
            row = ProfileWinItemWidget(i, pseudo, classe, enabled)
            row.toggled.connect(lambda s, item=it: self._on_row_toggled(item, s))
            self.windows_list.addItem(it)
            self.windows_list.setItemWidget(it, row)

    def _on_row_toggled(self, item: QListWidgetItem, enabled: bool):
        d = item.data(Qt.UserRole) or {}
        d["enabled"] = bool(enabled)
        item.setData(Qt.UserRole, d)

    def _update_indexes_after_drag(self):
        for i in range(self.windows_list.count()):
            it = self.windows_list.item(i)
            w = self.windows_list.itemWidget(it)
            if w:
                w.set_index(i)

    def _current_windows_array(self) -> list[dict]:
        arr = []
        for i in range(self.windows_list.count()):
            it = self.windows_list.item(i)
            d = it.data(Qt.UserRole) or {}
            arr.append({
                "pseudo": d.get("pseudo", ""),
                "classe": d.get("classe", ""),
                "enabled": bool(d.get("enabled", True)),
            })
        return arr

    def _save_profile_content(self):
        it = self.profiles_list.currentItem()
        if not it:
            QMessageBox.warning(self, "Profil", "Sélectionne un profil d’abord.")
            return
        name = it.text().strip()
        windows = self._current_windows_array()
        try:
            extra = {"global_hotkeys": {"next": self.profile_next_hotkey}} if self.profile_next_hotkey else {}
            save_profile(name, windows, extra=extra)
            QMessageBox.information(self, "Profil", "Profil enregistré.")
        except Exception as e:
            QMessageBox.critical(self, "Profil", f"Erreur: {e}")

    def _load_into_main(self):
        it = self.profiles_list.currentItem()
        if not it:
            return
        name = it.text()
        try:
            data = load_profile(name) or {}
            wins = data.get("windows", [])
            if hasattr(self.main, "_populate_list_from_windows"):
                self.main._populate_list_from_windows(wins)
                self.main._recompute_internal_order()
                self.main._adjust_height_to_list()
            # hotkey du profil (optionnel)
            hk = (data.get("global_hotkeys") or {}).get("next")
            if hk:
                self.main.hotkey_next = hk
                self.main.lbl_next.setText(hk)
                self.main._register_global_next()
        except Exception as e:
            QMessageBox.critical(self, "Charger", f"Erreur: {e}")

    def _new_from_open_windows(self):
        from core.window_manager import get_dofus_windows
        wins = get_dofus_windows() or []
        if not wins:
            QMessageBox.information(self, "Nouveau", "Aucune fenêtre Dofus détectée.")
            return
        name, ok = QtWidgets.QInputDialog.getText(self, "Nouveau profil", "Nom du profil :")
        if not ok or not name.strip():
            return
        name = name.strip()
        if name in get_profiles_list():
            QMessageBox.warning(self, "Profil", "Un profil existe déjà avec ce nom.")
            return
        try:
            wins2 = [{"pseudo": w.get("pseudo",""), "classe": w.get("classe",""), "enabled": True} for w in wins]
            save_profile(name, wins2)
            self._reload_profiles()
            self._select_profile(name)
        except Exception as e:
            QMessageBox.critical(self, "Nouveau", f"Erreur: {e}")

    def _rename_profile(self):
        import os
        from core.profiles import PROFILES_DIR, get_profiles_list
        it = self.profiles_list.currentItem()
        if not it:
            return
        old = it.text()
        new, ok = QtWidgets.QInputDialog.getText(self, "Renommer", f"Nouveau nom pour '{old}' :")
        if not ok or not new.strip():
            return
        new = new.strip()
        if new in get_profiles_list():
            QMessageBox.warning(self, "Profil", "Un profil existe déjà avec ce nom.")
            return
        try:
            os.rename(os.path.join(PROFILES_DIR, f"{old}.json"), os.path.join(PROFILES_DIR, f"{new}.json"))
            self._reload_profiles()
            self._select_profile(new)
        except Exception as e:
            QMessageBox.critical(self, "Renommer", f"Erreur: {e}")

    def _delete_profile(self):
        import os
        from core.profiles import PROFILES_DIR
        it = self.profiles_list.currentItem()
        if not it:
            return
        name = it.text().strip()
        if QMessageBox.question(self, "Supprimer", f"Supprimer le profil '{name}' ?") != QMessageBox.Yes:
            return
        try:
            os.remove(os.path.join(PROFILES_DIR, f"{name}.json"))
            self._reload_profiles()
            self.windows_list.clear()
            self.profile_next_hotkey = None
            self.lbl_profile_next.setText("")
        except Exception as e:
            QMessageBox.critical(self, "Supprimer", f"Erreur: {e}")

    def _select_profile(self, name: str):
        m = self.profiles_list.findItems(name, Qt.MatchExactly)
        if m:
            self.profiles_list.setCurrentItem(m[0])

    def _delete_window_entry(self):
        r = self.windows_list.currentRow()
        if r >= 0:
            self.windows_list.takeItem(r)
            self._update_indexes_after_drag()

    def _toggle_main_profile(self):
        QMessageBox.information(self, "Profil principal", "À connecter à la persistance si tu veux marquer un profil par défaut.")

    def _capture_profile_next_hotkey(self):
        dlg = HotkeyCaptureDialog("Raccourci 'Suivant' du profil", self)
        def _on_sel(hk: str):
            self.profile_next_hotkey = hk
            self.lbl_profile_next.setText(hk)
        dlg.hotkey_selected.connect(_on_sel)
        dlg.exec()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setWindowIcon(QtGui.QIcon("assets/icon/dwm.ico"))

    # si tu stockes le thème dans QSettings :
    from PySide6 import QtCore
    settings = QtCore.QSettings("DWM", "Organizer")
    theme_key = settings.value("ui/theme", "dark")

    apply_theme_to_app(app, theme_key)   

    window = DofusOrganizer()
    window.show()
    sys.exit(app.exec())
    self.drag = QLabel("⋮⋮", objectName="miniDrag")
