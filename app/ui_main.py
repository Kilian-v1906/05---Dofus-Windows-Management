"""
app/ui_main.py
Fenêtre principale et chef d'orchestre de l'application Dofus Organizer.
"""

import os
import sys
import win32gui
import keyboard

# S'assurer que la racine du projet est dans sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QListWidget, QListWidgetItem, QComboBox, QCheckBox, QMessageBox,
    QGraphicsDropShadowEffect, QMenu, QAbstractItemView
)
from PySide6.QtGui import QPixmap, QColor
from PySide6.QtCore import Qt, QSize, Signal, Slot, QTimer

from core.window_manager import get_dofus_windows
from core.profiles import (
    get_profiles_list,
    load_profile,
    get_primary_profile,
    is_profile_primary,
    find_best_matching_profile,
)
from utils.paths import (
    load_icon,
    icon_for_class,
    apply_theme_to_app,
    get_app_settings,
)
from utils.hotkeys import (
    normalize_hotkey_string,
    format_hotkey_display,
    register_hotkey_safe,
    unregister_hotkey_safe,
)
from utils.winfocus import force_foreground

from app.hotkey_dialog import HotkeyCaptureDialog
from app.mini_mode import MiniModeWindow
from app.profiles_dialog import ProfilesManagerDialog
from app.settings_dialog import SettingsDialog


# =============================================================================
# Carte d'un Personnage / Fenêtre (Main Window Card)
# =============================================================================

class WindowItemWidget(QWidget):
    hotkey_changed = Signal(object, str)
    toggled = Signal(object, bool)

    def __init__(
        self,
        index: int,
        pseudo: str,
        classe: str,
        handle: int,
        focus_enabled: bool = True,
        hotkey: str | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.pseudo = pseudo
        self.classe = classe
        self.handle = handle
        self.assigned_hotkey: str | None = None
        self._hotkey_hook_id: int | None = None

        self.setAttribute(Qt.WA_TranslucentBackground, True)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        card = QtWidgets.QFrame(objectName="card")
        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(16)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 100))
        card.setGraphicsEffect(shadow)

        grid = QtWidgets.QGridLayout(card)
        grid.setContentsMargins(12, 8, 12, 8)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(2)

        # Icône de classe
        self.icon = QLabel()
        pm = QPixmap(icon_for_class(self.classe))
        if not pm.isNull():
            pm = pm.scaled(38, 38, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.icon.setPixmap(pm)
        self.icon.setFixedSize(38, 38)
        self.icon.setAlignment(Qt.AlignCenter)

        # Pseudo & Classe
        info_box = QWidget()
        info_l = QVBoxLayout(info_box)
        info_l.setContentsMargins(0, 0, 0, 0)
        info_l.setSpacing(2)

        self.name_label = QLabel(self.pseudo)
        self.name_label.setStyleSheet("font-size:14px; font-weight:700;")
        self.class_label = QLabel(self.classe)
        self.class_label.setProperty("muted", True)
        info_l.addWidget(self.name_label)
        info_l.addWidget(self.class_label)

        # Contrôles de droite (Index + Toggle + Bouton Hotkey + Badge + Bouton Effacer)
        right_box = QWidget()
        right = QHBoxLayout(right_box)
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(6)

        self.index_label = QLabel(f"#{index+1}", objectName="indexBadge")

        self.focus_chk = QCheckBox()
        self.focus_chk.setChecked(bool(focus_enabled))
        self.focus_chk.stateChanged.connect(lambda s: self.toggled.emit(self, bool(s)))

        self.hotkey_btn = QPushButton("Raccourci...")
        self.hotkey_btn.setFixedHeight(28)
        self.hotkey_btn.clicked.connect(self._open_hotkey_dialog)

        self.hotkey_label = QLabel("")
        self.hotkey_label.setProperty("pill", True)
        self.hotkey_label.setAlignment(Qt.AlignCenter)
        self.hotkey_label.setMinimumWidth(44)
        self.hotkey_label.setVisible(False)

        self.clear_btn = QPushButton("✕")
        self.clear_btn.setFixedSize(26, 26)
        self.clear_btn.setObjectName("clearHotkeyBtn")
        self.clear_btn.setToolTip("Supprimer le raccourci de ce personnage")
        self.clear_btn.clicked.connect(self._on_clear_hotkey_clicked)
        self.clear_btn.setVisible(False)

        right.addWidget(self.index_label)
        right.addWidget(self.focus_chk)
        right.addWidget(self.hotkey_btn)
        right.addWidget(self.hotkey_label)
        right.addWidget(self.clear_btn)

        grid.addWidget(self.icon, 0, 0, 2, 1, Qt.AlignLeft | Qt.AlignVCenter)
        grid.addWidget(info_box, 0, 1, 2, 1)
        grid.addWidget(right_box, 0, 2, 2, 1, Qt.AlignRight | Qt.AlignVCenter)

        root.addWidget(card)

        if hotkey:
            self.set_account_hotkey(hotkey, silent=True)

    def set_index(self, i: int):
        self.index_label.setText(f"#{i+1}")

    def _open_hotkey_dialog(self):
        # Désactiver temporairement le hook actif pour éviter les conflits de touche pendant la capture
        old_hk = self.assigned_hotkey
        self._unregister_hook()

        dlg = HotkeyCaptureDialog(
            f"Raccourci pour {self.pseudo}",
            self,
            current_hotkey=old_hk or ""
        )
        dlg.hotkey_selected.connect(lambda hk: self._on_hotkey_captured(hk))
        dlg.exec()

    def _on_hotkey_captured(self, hk: str):
        if hk:
            self.set_account_hotkey(hk, silent=False)
        else:
            self.clear_account_hotkey()
            self.hotkey_changed.emit(self, "")

    def _on_clear_hotkey_clicked(self):
        self.clear_account_hotkey()
        self.hotkey_changed.emit(self, "")

    def set_account_hotkey(self, hotkey: str, silent: bool = False):
        """Enregistre le raccourci direct pour ce personnage."""
        self.clear_account_hotkey()

        normalized = normalize_hotkey_string(hotkey)
        if not normalized:
            return

        self.assigned_hotkey = normalized
        self.hotkey_label.setText(format_hotkey_display(normalized))
        self.hotkey_label.setVisible(True)
        self.clear_btn.setVisible(True)

        def _focus_callback():
            if self.handle:
                force_foreground(self.handle)

        hid = register_hotkey_safe(normalized, _focus_callback, suppress=False)
        if hid is not None:
            self._hotkey_hook_id = hid
            if not silent:
                self.hotkey_changed.emit(self, normalized)
        else:
            self.assigned_hotkey = None
            self.hotkey_label.setText("")
            self.hotkey_label.setVisible(False)
            self.clear_btn.setVisible(False)
            if not silent:
                QMessageBox.warning(self, "Raccourci", f"Impossible d'enregistrer la combinaison : {hotkey}")

    def _unregister_hook(self):
        if self._hotkey_hook_id is not None:
            unregister_hotkey_safe(self._hotkey_hook_id)
            self._hotkey_hook_id = None

    def clear_account_hotkey(self):
        """Retire le raccourci dédié à ce compte."""
        self._unregister_hook()
        self.assigned_hotkey = None
        self.hotkey_label.setText("")
        self.hotkey_label.setVisible(False)
        self.clear_btn.setVisible(False)

    def contextMenuEvent(self, e: QtGui.QContextMenuEvent):
        menu = QMenu(self)
        a_set = menu.addAction("Définir un raccourci...")
        a_clear = menu.addAction("Supprimer le raccourci")
        chosen = menu.exec(e.globalPos())
        if chosen == a_set:
            self._open_hotkey_dialog()
        elif chosen == a_clear:
            self.clear_account_hotkey()
            self.hotkey_changed.emit(self, "")


# =============================================================================
# Fenêtre Principale Dofus Organizer
# =============================================================================

class DofusOrganizer(QWidget):
    focus_next_requested = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Dofus Organizer")
        ico = load_icon("dwm.ico")
        if not ico.isNull():
            self.setWindowIcon(ico)
        self.setMinimumWidth(500)
        self.setMaximumWidth(580)

        self.settings = get_app_settings()

        self.ordered_handles: list[int] = []
        self.current_index: int = 0
        self._auto_profile_name: str | None = None

        # Raccourcis globaux
        self._hk_next_id: int | None = None
        self._hk_prev_id: int | None = None

        self.hotkey_next = normalize_hotkey_string(self.settings.value("hotkeys/global_next", "tab"))
        self.hotkey_prev = normalize_hotkey_string(self.settings.value("hotkeys/global_prev", "shift+tab"))

        self._mini: MiniModeWindow | None = None

        # Construction du layout
        root = QVBoxLayout(self)
        root.setSpacing(12)
        root.setContentsMargins(14, 14, 14, 14)

        # En-tête
        header = self._setup_header()
        root.addLayout(header)

        # Liste des cartes
        self.list = QListWidget()
        self.list.setSpacing(8)
        self.list.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.list.setDragDropMode(QListWidget.InternalMove)
        self.list.model().rowsMoved.connect(self._update_indexes_after_drag)
        self.list.itemDoubleClicked.connect(self._on_card_double_clicked)
        root.addWidget(self.list)

        # Barre de statut
        self.status_row = QHBoxLayout()
        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("font-size:12px;")
        self.status_row.addWidget(self.lbl_status)
        self.status_row.addStretch()
        root.addLayout(self.status_row)

        # Barre d'actions inférieure
        bottom = QHBoxLayout()
        bottom.setSpacing(10)

        self.refresh_order_btn = QPushButton("Actualiser les fenêtres")
        self.refresh_order_btn.setIcon(load_icon("refresh.svg"))
        self.refresh_order_btn.setIconSize(QSize(16, 16))
        self.refresh_order_btn.setProperty("neon", "primary")
        self.refresh_order_btn.clicked.connect(self._refresh_and_apply_order)

        self.play_btn = QPushButton("Jouer")
        self.play_btn.setIcon(load_icon("play.svg"))
        self.play_btn.setIconSize(QSize(16, 16))
        self.play_btn.setProperty("neon", "success")
        self.play_btn.clicked.connect(self._play_and_minimize)

        bottom.addWidget(self.refresh_order_btn)
        bottom.addWidget(self.play_btn)
        root.addLayout(bottom)

        # Initialisation du contenu
        self._populate_from_detected_only()
        self._adjust_height_to_list()
        self._register_global_hotkeys()
        self._update_status()

        # Timer de surveillance périodique des fenêtres Dofus ouvertes (1 seconde)
        self._win_monitor_timer = QTimer(self)
        self._win_monitor_timer.setInterval(1000)
        self._win_monitor_timer.timeout.connect(self._check_dofus_windows_alive)
        self._win_monitor_timer.start()

        # Vérification des mises à jour au démarrage après 2.5 secondes
        self._startup_update_worker = None
        QTimer.singleShot(2500, self._check_update_on_startup)


    def _setup_header(self) -> QtWidgets.QLayout:
        grid = QtWidgets.QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)
        grid.setContentsMargins(0, 0, 0, 0)

        # Profil (Ligne 1)
        lbl_prof = QLabel("Profil :")
        lbl_prof.setStyleSheet("font-weight:600;")
        self.profile_combo = QComboBox()
        self.profile_combo.setMinimumWidth(260)
        self._reload_profiles_combo()
        self.profile_combo.currentIndexChanged.connect(self._on_profile_changed_index)

        self.manage_btn = QPushButton("Gérer les profils")
        self.manage_btn.setIcon(load_icon("account.svg"))
        self.manage_btn.setIconSize(QSize(16, 16))
        self.manage_btn.setFixedHeight(32)
        self.manage_btn.clicked.connect(self._open_profiles_manager)

        self.settings_btn = QPushButton("")
        self.settings_btn.setObjectName("settingsIcon")
        ico = load_icon("settings.svg")
        if not ico.isNull():
            self.settings_btn.setIcon(ico)
        else:
            self.settings_btn.setText("⚙")
        self.settings_btn.setIconSize(QSize(18, 18))
        self.settings_btn.setFixedSize(36, 36)
        self.settings_btn.setToolTip("Paramètres")
        self.settings_btn.clicked.connect(self._open_settings)

        row_right = QHBoxLayout()
        row_right.setContentsMargins(0, 0, 0, 0)
        row_right.setSpacing(8)
        row_right.addWidget(self.manage_btn)
        row_right.addWidget(self.settings_btn)

        grid.addWidget(lbl_prof, 0, 0, 1, 1, Qt.AlignLeft | Qt.AlignVCenter)
        grid.addWidget(self.profile_combo, 0, 1, 1, 1)
        grid.addLayout(row_right, 0, 2, 1, 1, Qt.AlignRight | Qt.AlignVCenter)

        # Raccourcis Globaux Suivant & Précédent (Ligne 2)
        hk_row = QHBoxLayout()
        hk_row.setContentsMargins(0, 0, 0, 0)
        hk_row.setSpacing(6)

        # Suivant
        self.btn_set_next = QPushButton("Suivant...")
        self.btn_set_next.setIcon(load_icon("arrow-right.svg"))
        self.btn_set_next.setIconSize(QSize(14, 14))
        self.btn_set_next.setFixedHeight(30)
        self.btn_set_next.clicked.connect(self._capture_global_next_hotkey)

        self.lbl_next = QLabel(format_hotkey_display(self.hotkey_next))
        self.lbl_next.setObjectName("hotkeyBadge")
        self.lbl_next.setAlignment(Qt.AlignCenter)
        self.lbl_next.setMinimumWidth(56)

        self.btn_clear_next = QPushButton("✕")
        self.btn_clear_next.setFixedSize(26, 26)
        self.btn_clear_next.setToolTip("Effacer le raccourci Suivant")
        self.btn_clear_next.clicked.connect(lambda: self.set_next_hotkey(""))

        # Précédent
        self.btn_set_prev = QPushButton("Précédent...")
        self.btn_set_prev.setFixedHeight(30)
        self.btn_set_prev.clicked.connect(self._capture_global_prev_hotkey)

        self.lbl_prev = QLabel(format_hotkey_display(self.hotkey_prev))
        self.lbl_prev.setObjectName("hotkeyBadge")
        self.lbl_prev.setAlignment(Qt.AlignCenter)
        self.lbl_prev.setMinimumWidth(56)

        self.btn_clear_prev = QPushButton("✕")
        self.btn_clear_prev.setFixedSize(26, 26)
        self.btn_clear_prev.setToolTip("Effacer le raccourci Précédent")
        self.btn_clear_prev.clicked.connect(lambda: self.set_prev_hotkey(""))

        hk_row.addWidget(self.btn_set_next)
        hk_row.addWidget(self.lbl_next)
        hk_row.addWidget(self.btn_clear_next)
        hk_row.addSpacing(10)
        hk_row.addWidget(self.btn_set_prev)
        hk_row.addWidget(self.lbl_prev)
        hk_row.addWidget(self.btn_clear_prev)
        hk_row.addStretch()

        grid.addLayout(hk_row, 1, 0, 1, 3)

        return grid

    # ----- Gestion des Profils dans la Combo -----
    def _reload_profiles_combo(self):
        """Recharge la combobox des profils avec filtrage par fenêtres ouvertes et affichage du profil auto."""
        open_pseudos = {w["pseudo"].lower() for w in get_dofus_windows()}

        compatible = []
        for name in get_profiles_list():
            data = load_profile(name)
            if not data:
                continue
            needed = [str(w.get("pseudo", "")).strip().lower() for w in data.get("windows", []) if w.get("pseudo")]
            if needed and set(needed).issubset(open_pseudos):
                is_prim = is_profile_primary(name)
                compatible.append((name, is_prim))

        self.profile_combo.blockSignals(True)
        prev_data = self.profile_combo.currentData()
        self.profile_combo.clear()

        # Libellé dynamique affichant le profil sélectionné si auto-détection
        auto_enabled = bool(self.settings.value("profiles/auto_detect_enabled", True, bool))
        if auto_enabled:
            if self._auto_profile_name:
                auto_label = f"Détection automatique ({self._auto_profile_name})"
            else:
                auto_label = "Détection automatique (Aucun profil détecté)"
            self.profile_combo.addItem(auto_label, userData="__auto__")
        else:
            self.profile_combo.addItem("Sélection manuelle (Auto désactivée)", userData="__manual__")

        for name, is_prim in compatible:
            display = f"★ {name}" if is_prim else name
            self.profile_combo.addItem(display, userData=name)

        # Restauration de la sélection
        target_idx = 0
        if prev_data:
            for i in range(self.profile_combo.count()):
                if self.profile_combo.itemData(i) == prev_data:
                    target_idx = i
                    break
        self.profile_combo.setCurrentIndex(target_idx)

        self.profile_combo.blockSignals(False)

    def _on_profile_changed_index(self, index: int):
        data_tag = self.profile_combo.itemData(index)
        if data_tag in ("__auto__", "__manual__") or index <= 0:
            self._populate_from_detected_only()
            return

        name = data_tag or self.profile_combo.itemText(index).replace("★ ", "").strip()
        data = load_profile(name)
        if not data:
            return

        # Raccourcis du profil (Suivant et Précédent)
        ghk = data.get("global_hotkeys") or {}
        hk_next = ghk.get("next")
        if hk_next:
            self.set_next_hotkey(hk_next)
        hk_prev = ghk.get("prev")
        if hk_prev:
            self.set_prev_hotkey(hk_prev)

        windows = data.get("windows", [])
        # Associer les handles réels
        current_map = {w["pseudo"].lower(): w for w in get_dofus_windows()}
        merged = []
        seen_handles = set()
        for w in windows:
            pseudo = str(w.get("pseudo", "")).strip()
            item = dict(w)
            if pseudo.lower() in current_map:
                h = current_map[pseudo.lower()]["handle"]
                if h in seen_handles:
                    continue
                seen_handles.add(h)
                item["handle"] = h
            merged.append(item)

        self._auto_profile_name = name
        self._populate_list_from_windows(merged)
        self._recompute_internal_order()
        self._adjust_height_to_list()

    # ----- Remplissage de la liste des personnages -----
    def _populate_from_detected_only(self):
        detected = get_dofus_windows()
        open_pseudos = [w["pseudo"] for w in detected]
        current_map = {w["pseudo"].lower(): w for w in detected}

        auto_enabled = bool(self.settings.value("profiles/auto_detect_enabled", True, bool))

        # Détection automatique du profil le plus adapté si autorisée
        if auto_enabled:
            best_name, best_data = find_best_matching_profile(open_pseudos)
        else:
            best_name, best_data = None, None

        if best_name and best_data:
            self._auto_profile_name = best_name
            # Charger les raccourcis du profil automatique
            ghk = best_data.get("global_hotkeys") or {}
            if ghk.get("next"):
                self.set_next_hotkey(ghk["next"])
            if ghk.get("prev"):
                self.set_prev_hotkey(ghk["prev"])

            prof_wins = best_data.get("windows", [])
            merged = []
            used_pseudos = set()
            used_handles = set()

            # Personnages définis dans le profil ordonné
            for w in prof_wins:
                p_clean = str(w.get("pseudo", "")).strip()
                if p_clean.lower() in current_map:
                    real_w = current_map[p_clean.lower()]
                    h = real_w["handle"]
                    if h in used_handles:
                        continue
                    item = dict(w)
                    item["handle"] = h
                    merged.append(item)
                    used_pseudos.add(p_clean.lower())
                    used_handles.add(h)

            # Ajouter d'éventuelles autres fenêtres ouvertes non listées dans le profil
            for w in detected:
                h = w["handle"]
                p_lower = w["pseudo"].strip().lower()
                if p_lower not in used_pseudos and h not in used_handles:
                    merged.append({
                        "pseudo": w["pseudo"],
                        "classe": w["classe"],
                        "handle": h,
                        "enabled": True,
                        "hotkey": None,
                    })
                    used_pseudos.add(p_lower)
                    used_handles.add(h)

            self._populate_list_from_windows(merged)
        else:
            self._auto_profile_name = None
            seen_h = set()
            dedup_detected = []
            for w in detected:
                h = w["handle"]
                if h not in seen_h:
                    seen_h.add(h)
                    w.setdefault("enabled", True)
                    w.setdefault("hotkey", None)
                    dedup_detected.append(w)
            self._populate_list_from_windows(dedup_detected)

        self._recompute_internal_order()
        self._adjust_height_to_list()
        self._reload_profiles_combo()

    def _populate_list_from_windows(self, windows: list[dict]):
        self.list.clear()
        for i, w in enumerate(windows):
            item = QListWidgetItem()
            card = WindowItemWidget(
                index=i,
                pseudo=w.get("pseudo", ""),
                classe=w.get("classe", ""),
                handle=w.get("handle", 0),
                focus_enabled=bool(w.get("enabled", True)),
                hotkey=w.get("hotkey"),
                parent=self.list,
            )
            card.toggled.connect(self._on_card_toggled)
            card.hotkey_changed.connect(self._on_card_hotkey_changed)
            item.setSizeHint(QSize(0, 64))
            self.list.addItem(item)
            self.list.setItemWidget(item, card)

        self._update_status()

    def _on_card_hotkey_changed(self, _widget, _hotkey: str):
        # Mettre à jour si nécessaire
        pass

    def _on_card_toggled(self, _widget, _enabled: bool):
        self._recompute_internal_order()
        self._update_status()
        if self._mini:
            self._mini.reorder_from_main(self.ordered_handles)

    def _update_indexes_after_drag(self):
        for i in range(self.list.count()):
            w = self.list.itemWidget(self.list.item(i))
            if isinstance(w, WindowItemWidget):
                w.set_index(i)
        self._recompute_internal_order()
        self._update_status()
        if self._mini:
            self._mini.reorder_from_main(self.ordered_handles)

    def _adjust_height_to_list(self):
        """Ajuste dynamiquement la hauteur de la fenêtre pour afficher au minimum 8 comptes sans scrollbar."""
        n = max(1, self.list.count())
        item_h = 64
        spacing = 8
        extra_padding = 28

        screen = QtGui.QGuiApplication.primaryScreen()
        screen_h = screen.availableGeometry().height() if screen else 900
        max_allowed_total = int(screen_h * 0.90)

        # Hauteur calculée pour afficher au minimum 8 comptes sans scrollbar
        eight_items_h = (8 * item_h) + (7 * spacing) + 72  # 640 px

        if n <= 8:
            # Jusqu'à 8 personnages : pas de barre de défilement verticale
            self.list.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            self.list.setFixedHeight(eight_items_h)
        else:
            # Plus de 8 personnages : affichage de 8 cartes et scrollbar verticale
            self.list.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            self.list.setFixedHeight(eight_items_h)

        self.setMinimumHeight(0)
        self.setMaximumHeight(16777215)
        self.adjustSize()

        total_h = min(self.height(), max_allowed_total)
        self.setFixedHeight(total_h)

    def _update_status(self):
        total = self.list.count()
        included = sum(
            1 for i in range(total)
            if getattr(self.list.itemWidget(self.list.item(i)), "focus_chk", None)
            and self.list.itemWidget(self.list.item(i)).focus_chk.isChecked()
        )
        if self.profile_combo.currentIndex() <= 0:
            if self._auto_profile_name:
                prof = f"Auto ({self._auto_profile_name})"
            else:
                prof = "Auto"
        else:
            prof = self.profile_combo.currentText() or "Manuel"

        self.lbl_status.setText(f"Fenêtres : {included}/{total} actives  |  Profil : {prof}")

    def _recompute_internal_order(self):
        handles = []
        for i in range(self.list.count()):
            w = self.list.itemWidget(self.list.item(i))
            if isinstance(w, WindowItemWidget) and w.focus_chk.isChecked() and w.handle:
                handles.append(w.handle)
        self.ordered_handles = handles
        self.current_index = 0

    def sync_active_handle(self, hwnd: int):
        """
        Synchronise l'index de rotation lorsqu'une fenêtre Dofus prend le focus
        (clic manuel dans la barre des tâches, clic dans le jeu ou sur le mini-mode).
        """
        if not hwnd or not self.ordered_handles:
            return
        if hwnd in self.ordered_handles:
            new_idx = self.ordered_handles.index(hwnd)
            if self.current_index != new_idx:
                self.current_index = new_idx
                if self._mini:
                    self._mini.set_active_handle(hwnd)

    # ----- Raccourcis Globaux Suivant & Précédent -----
    def _register_global_hotkeys(self):
        # Désenregistrement préalable
        if self._hk_next_id is not None:
            unregister_hotkey_safe(self._hk_next_id)
            self._hk_next_id = None
        if self._hk_prev_id is not None:
            unregister_hotkey_safe(self._hk_prev_id)
            self._hk_prev_id = None

        if self.hotkey_next:
            self._hk_next_id = register_hotkey_safe(
                self.hotkey_next,
                lambda: QtCore.QMetaObject.invokeMethod(self, "_do_focus_next", Qt.QueuedConnection),
                suppress=False,
            )

        if self.hotkey_prev:
            self._hk_prev_id = register_hotkey_safe(
                self.hotkey_prev,
                lambda: QtCore.QMetaObject.invokeMethod(self, "_do_focus_prev", Qt.QueuedConnection),
                suppress=False,
            )

    def set_next_hotkey(self, hk: str):
        normalized = normalize_hotkey_string(hk)
        self.hotkey_next = normalized
        self.lbl_next.setText(format_hotkey_display(normalized))
        self.settings.setValue("hotkeys/global_next", normalized)
        self._register_global_hotkeys()
        if self._mini:
            self._mini.set_next_hotkey_label(normalized)

    def set_prev_hotkey(self, hk: str):
        normalized = normalize_hotkey_string(hk)
        self.hotkey_prev = normalized
        self.lbl_prev.setText(format_hotkey_display(normalized))
        self.settings.setValue("hotkeys/global_prev", normalized)
        self._register_global_hotkeys()

    def _capture_global_next_hotkey(self):
        dlg = HotkeyCaptureDialog("Raccourci global - Suivant", self, current_hotkey=self.hotkey_next)
        dlg.hotkey_selected.connect(self.set_next_hotkey)
        dlg.exec()

    def _capture_global_prev_hotkey(self):
        dlg = HotkeyCaptureDialog("Raccourci global - Précédent", self, current_hotkey=self.hotkey_prev)
        dlg.hotkey_selected.connect(self.set_prev_hotkey)
        dlg.exec()

    @Slot()
    def _do_focus_next(self):
        if not self.ordered_handles:
            self._recompute_internal_order()
            if not self.ordered_handles:
                return

        # Synchronisation immédiate avec la fenêtre actuellement au premier plan
        try:
            fg = win32gui.GetForegroundWindow()
            if fg and fg in self.ordered_handles:
                self.current_index = self.ordered_handles.index(fg)
        except Exception:
            pass

        self.current_index = (self.current_index + 1) % len(self.ordered_handles)
        hwnd = self.ordered_handles[self.current_index]
        self._focus_handle(hwnd)

    @Slot()
    def _do_focus_prev(self):
        if not self.ordered_handles:
            self._recompute_internal_order()
            if not self.ordered_handles:
                return

        # Synchronisation immédiate avec la fenêtre actuellement au premier plan
        try:
            fg = win32gui.GetForegroundWindow()
            if fg and fg in self.ordered_handles:
                self.current_index = self.ordered_handles.index(fg)
        except Exception:
            pass

        self.current_index = (self.current_index - 1) % len(self.ordered_handles)
        hwnd = self.ordered_handles[self.current_index]
        self._focus_handle(hwnd)

    def _focus_handle(self, hwnd: int):
        self.sync_active_handle(hwnd)
        delay = int(self.settings.value("win32/delay_ms", 20))
        force_foreground(hwnd, delay_ms=delay)

    def _on_card_double_clicked(self, item: QListWidgetItem):
        w = self.list.itemWidget(item)
        if isinstance(w, WindowItemWidget) and w.handle:
            self._recompute_internal_order()
            if w.handle in self.ordered_handles:
                self.current_index = self.ordered_handles.index(w.handle)
            self._focus_handle(w.handle)

    # ----- Surveillance en temps réel des fenêtres fermées -----
    def _check_dofus_windows_alive(self):
        """Vérifie si des fenêtres Dofus ont été fermées par l'utilisateur."""
        active = get_dofus_windows()
        active_handles = {w["handle"] for w in active}
        active_pseudos = {w["pseudo"].lower() for w in active}

        # Identifier les éléments dont le handle n'existe plus
        dead_rows = []
        for i in range(self.list.count()):
            w = self.list.itemWidget(self.list.item(i))
            if isinstance(w, WindowItemWidget):
                if w.handle and (w.handle not in active_handles or not win32gui.IsWindow(w.handle)):
                    dead_rows.append((i, w.handle))

        if not dead_rows:
            return

        # Supprimer les fenêtres fermées de la liste (en partant de la fin pour garder les index stables)
        for row_idx, h in reversed(dead_rows):
            it = self.list.takeItem(row_idx)
            card = self.list.itemWidget(it)
            if isinstance(card, WindowItemWidget):
                card.clear_account_hotkey()
            if self._mini:
                self._mini.remove_handle(h)

        # Mettre à jour les index visuels
        for i in range(self.list.count()):
            w = self.list.itemWidget(self.list.item(i))
            if isinstance(w, WindowItemWidget):
                w.set_index(i)

        self._recompute_internal_order()
        self._adjust_height_to_list()

        # Vérifier si le profil sélectionné est toujours complet
        current_idx = self.profile_combo.currentIndex()
        if current_idx > 0:
            name = self.profile_combo.itemData(current_idx) or self.profile_combo.itemText(current_idx).replace("★ ", "").strip()
            data = load_profile(name)
            if data:
                needed = [str(w.get("pseudo", "")).strip().lower() for w in data.get("windows", []) if w.get("pseudo")]
                if needed and not set(needed).issubset(active_pseudos):
                    # Le profil n'est plus complet -> réinitialiser sur détection automatique
                    self.profile_combo.setCurrentIndex(0)
                    self._populate_from_detected_only()
                    return

        if current_idx <= 0:
            # Réévaluer la détection automatique pour le nouveau sous-ensemble
            best_name, _ = find_best_matching_profile([w["pseudo"] for w in active])
            self._auto_profile_name = best_name

        self._reload_profiles_combo()
        self._update_status()

        # Synchroniser l'index actif si l'utilisateur est sur une fenêtre Dofus
        try:
            fg = win32gui.GetForegroundWindow()
            if fg and fg in self.ordered_handles:
                self.sync_active_handle(fg)
        except Exception:
            pass

    # ----- Actions boutons -----
    def _refresh_and_apply_order(self):
        """Rafraîchit la liste des fenêtres ouvertes et synchronise."""
        idx = self.profile_combo.currentIndex()
        if idx <= 0:
            self._populate_from_detected_only()
        else:
            self._on_profile_changed_index(idx)
        self._update_status()

    def _play_and_minimize(self):
        """Lance le mode Mini-HUD et donne le focus au personnage #1."""
        self._recompute_internal_order()
        if not self.ordered_handles:
            QMessageBox.information(self, "Jouer", "Aucune fenêtre Dofus active sélectionnée.")
            return

        if self._mini is not None:
            try:
                self._mini.hide()
                self._mini.close()
                self._mini.deleteLater()
            except Exception:
                pass
            self._mini = None

        windows = []
        seen_handles = set()
        for i in range(self.list.count()):
            card = self.list.itemWidget(self.list.item(i))
            if isinstance(card, WindowItemWidget):
                h = card.handle
                if h and h in seen_handles:
                    continue
                if h:
                    seen_handles.add(h)
                windows.append({
                    "pseudo": card.pseudo,
                    "classe": card.classe,
                    "handle": card.handle,
                    "enabled": card.focus_chk.isChecked(),
                })

        self._mini = MiniModeWindow(self, windows)
        self._mini.show()
        self._mini.raise_()
        self._mini.activateWindow()
        self.hide()

        first_hwnd = self.ordered_handles[0]
        self._focus_handle(first_hwnd)

    def set_focus_enabled_for_handle(self, handle: int, enabled: bool):
        for i in range(self.list.count()):
            w = self.list.itemWidget(self.list.item(i))
            if isinstance(w, WindowItemWidget) and w.handle == handle:
                w.focus_chk.setChecked(bool(enabled))
                break
        self._recompute_internal_order()
        self._update_status()

    def _open_profiles_manager(self):
        dlg = ProfilesManagerDialog(self)
        dlg.exec()
        self._reload_profiles_combo()
        self._update_status()

    def _open_settings(self):
        dlg = SettingsDialog(self)
        if dlg.exec() == QtWidgets.QDialog.Accepted:
            self._reload_profiles_combo()
            self._refresh_and_apply_order()
            if self._mini:
                self._mini.refresh_settings_from_app()

    def _check_update_on_startup(self):
        """Vérifie silencieusement en arrière-plan s'il existe une nouvelle version."""
        if not bool(self.settings.value("updates/check_on_startup", True, bool)):
            return

        from core.updater import UpdateCheckerWorker
        from app.update_dialog import UpdateDialog

        self._startup_update_worker = UpdateCheckerWorker(self)

        def on_finished(res: dict):
            if res.get("update_available") and not self.isHidden():
                dlg = UpdateDialog(res, self)
                dlg.exec()

        self._startup_update_worker.check_finished.connect(on_finished)
        self._startup_update_worker.start()

    def closeEvent(self, event: QtGui.QCloseEvent):
        """Nettoie tous les hooks clavier et timers à la fermeture de l'application."""
        try:
            self._win_monitor_timer.stop()
        except Exception:
            pass

        if self._startup_update_worker and self._startup_update_worker.isRunning():
            try:
                self._startup_update_worker.terminate()
                self._startup_update_worker.wait(500)
            except Exception:
                pass

        if self._hk_next_id is not None:
            unregister_hotkey_safe(self._hk_next_id)
        if self._hk_prev_id is not None:
            unregister_hotkey_safe(self._hk_prev_id)


        for i in range(self.list.count()):
            w = self.list.itemWidget(self.list.item(i))
            if isinstance(w, WindowItemWidget):
                w.clear_account_hotkey()

        if self._mini:
            try:
                self._mini.close()
            except Exception:
                pass

        super().closeEvent(event)
