"""
app/mini_mode.py
Overlay HUD compact et transparent affiché en jeu lors du mode "Jouer".
"""

import time
import win32gui
import win32con

from PySide6 import QtWidgets, QtGui, QtCore
from PySide6.QtCore import Qt, QPoint, QTimer, Signal

from utils.paths import icon_for_class, load_icon
from utils.winfocus import force_foreground
from utils.hotkeys import format_hotkey_display
from utils.dwm_thumbnail import DwmThumbnailWidget, DwmHoverPreviewPopup, is_dwm_available
from app.settings_dialog import SettingsDialog

# Métriques compactes et épurées pour un HUD discret
MINI_H_COMPACT = 50
MINI_H_PIP = 126
CARD_H_COMPACT = 42
CARD_H_PIP = 118
MINI_CARD_W = 124
MINI_THUMB_H = 68
MINI_ICON_SIZE = 22
MINI_SPACING = 4
DRAG_BAR_W = 16
ROOT_PADDING = 4


class MiniCardItem(QtWidgets.QFrame):
    """Carte d'un personnage dans l'overlay mini-mode avec support du mode PiP (Live Thumbnail)."""

    toggled = Signal(int, bool)         # (handle, enabled)
    request_focus = Signal(int)         # (handle)
    hover_entered = Signal(object)      # (self)
    hover_left = Signal(object)         # (self)

    def __init__(self, index: int, pseudo: str, classe: str, handle: int, enabled: bool):
        super().__init__(objectName="miniCard")
        self.handle = handle
        self.pseudo = pseudo
        self.classe = classe
        self.enabled = bool(enabled)
        self.is_active = False
        self.pip_enabled = False

        self.setFixedSize(MINI_CARD_W, CARD_H_COMPACT)

        card_v = QtWidgets.QVBoxLayout(self)
        card_v.setContentsMargins(4, 2, 4, 3)
        card_v.setSpacing(2)

        # Ligne 1 : En-tête compact (Icône + Pseudo/Classe + Index/Toggle)
        hdr_w = QtWidgets.QWidget()
        lay = QtWidgets.QHBoxLayout(hdr_w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)

        # 1. Icône de classe
        self.icon = QtWidgets.QLabel()
        pm = QtGui.QPixmap(icon_for_class(classe))
        if not pm.isNull():
            pm = pm.scaled(MINI_ICON_SIZE, MINI_ICON_SIZE, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.icon.setPixmap(pm)
        self.icon.setFixedSize(MINI_ICON_SIZE, MINI_ICON_SIZE)
        self.icon.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.icon, 0, Qt.AlignVCenter | Qt.AlignLeft)

        # 2. Colonne Pseudo & Classe
        mid_col = QtWidgets.QVBoxLayout()
        mid_col.setContentsMargins(0, 0, 0, 0)
        mid_col.setSpacing(0)

        self.pseudo_lbl = QtWidgets.QLabel(pseudo)
        self.pseudo_lbl.setStyleSheet("font-size:10px; font-weight:700;")
        metrics = QtGui.QFontMetrics(self.pseudo_lbl.font())
        elided = metrics.elidedText(pseudo, Qt.ElideRight, 60)
        self.pseudo_lbl.setText(elided)
        self.pseudo_lbl.setToolTip(pseudo)

        self.class_lbl = QtWidgets.QLabel(classe)
        self.class_lbl.setProperty("muted", True)
        self.class_lbl.setStyleSheet("font-size:9px; font-weight:500;")

        mid_col.addWidget(self.pseudo_lbl, 0, Qt.AlignLeft | Qt.AlignVCenter)
        mid_col.addWidget(self.class_lbl, 0, Qt.AlignLeft | Qt.AlignVCenter)
        lay.addLayout(mid_col, 1)

        # 3. Colonne droite : Badge Index + Checkbox
        right_col = QtWidgets.QVBoxLayout()
        right_col.setContentsMargins(0, 0, 0, 0)
        right_col.setSpacing(1)

        self._idx_lbl = QtWidgets.QLabel(f"#{index+1}", objectName="miniIndex")
        self._idx_lbl.setAlignment(Qt.AlignCenter)

        self.chk = QtWidgets.QCheckBox()
        self.chk.setChecked(self.enabled)
        self.chk.stateChanged.connect(lambda s: self.toggled.emit(self.handle, bool(s)))

        right_col.addWidget(self._idx_lbl, 0, Qt.AlignRight | Qt.AlignVCenter)
        right_col.addWidget(self.chk, 0, Qt.AlignRight | Qt.AlignVCenter)
        lay.addLayout(right_col, 0)

        card_v.addWidget(hdr_w, 0)

        # Ligne 2 : Boîte d'aperçu miniature DWM PiP (vidéo en direct)
        self.thumb_box = QtWidgets.QFrame(objectName="miniThumbBox")
        self.thumb_box.setFixedHeight(MINI_THUMB_H)
        thumb_l = QtWidgets.QVBoxLayout(self.thumb_box)
        thumb_l.setContentsMargins(0, 0, 0, 0)
        thumb_l.setSpacing(0)

        self.thumb = DwmThumbnailWidget(self.handle, self.thumb_box)
        self.thumb.setFixedHeight(MINI_THUMB_H)
        self.thumb.clicked.connect(lambda: self.request_focus.emit(self.handle))
        thumb_l.addWidget(self.thumb)

        card_v.addWidget(self.thumb_box, 1)
        self.thumb_box.setVisible(False)

    def mouseReleaseEvent(self, e: QtGui.QMouseEvent):
        pos = e.position().toPoint() if hasattr(e, "position") else e.pos()
        child = self.childAt(pos)
        if not isinstance(child, QtWidgets.QCheckBox):
            self.request_focus.emit(self.handle)
        super().mouseReleaseEvent(e)

    def set_pip_enabled(self, enabled: bool):
        """Active ou désactive l'affichage du flux miniature PiP sous la carte."""
        self.pip_enabled = bool(enabled)
        card_h = CARD_H_PIP if self.pip_enabled else CARD_H_COMPACT
        self.setFixedSize(MINI_CARD_W, card_h)
        self.thumb_box.setVisible(self.pip_enabled)
        if self.pip_enabled:
            self.thumb.register()
        else:
            self.thumb.unregister()

    def set_index(self, i: int):
        self._idx_lbl.setText(f"#{i+1}")

    def set_active(self, active: bool):
        """Active ou désactive la mise en avant visuelle de la carte."""
        if self.is_active == active:
            return
        self.is_active = active
        self.setProperty("active", bool(active))
        self._idx_lbl.setProperty("active", bool(active))
        self.style().unpolish(self)
        self.style().polish(self)
        self._idx_lbl.style().unpolish(self._idx_lbl)
        self._idx_lbl.style().polish(self._idx_lbl)

    def enterEvent(self, event):
        super().enterEvent(event)
        self.hover_entered.emit(self)

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self.hover_left.emit(self)


class MiniModeWindow(QtWidgets.QWidget):
    """Overlay flottant compact affiché pendant le jeu."""

    def __init__(self, parent_main: QtWidgets.QWidget, windows: list[dict]):
        super().__init__(parent_main)
        self.main = parent_main

        # Dédoublonner strictement par handle
        seen_handles = set()
        dedup_windows = []
        for w in windows:
            h = w.get("handle")
            if h:
                if h not in seen_handles:
                    seen_handles.add(h)
                    dedup_windows.append(w)
            else:
                dedup_windows.append(w)
        self.windows = dedup_windows[:8]

        self.hide_outside_dofus = bool(self.main.settings.value("mini/hide_outside", True, bool))
        self.always_on_top = bool(self.main.settings.value("mini/always_on_top", False, bool))
        self.is_locked = bool(self.main.settings.value("mini/locked", False, bool))
        self.pip_enabled = bool(self.main.settings.value("mini/pip_enabled", False, bool))
        self.pip_hover_enabled = bool(self.main.settings.value("mini/pip_hover_enabled", True, bool))
        self._hover_popup: DwmHoverPreviewPopup | None = None
        self._opened_at = time.monotonic()
        self._active_handle: int | None = None

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        ico = load_icon("dwm.ico")
        if not ico.isNull():
            self.setWindowIcon(ico)

        # Opacité configurée
        op = int(self.main.settings.value("mini/opacity", 90))
        self.setWindowOpacity(max(0.2, min(1.0, op / 100.0)))

        root = QtWidgets.QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Cadre conteneur principal HUD
        self.cont = QtWidgets.QFrame(objectName="miniRoot")
        self.cont.setFixedHeight(MINI_H_PIP if self.pip_enabled else MINI_H_COMPACT)

        cv = QtWidgets.QHBoxLayout(self.cont)
        cv.setContentsMargins(ROOT_PADDING, ROOT_PADDING, ROOT_PADDING, ROOT_PADDING)
        cv.setSpacing(MINI_SPACING)

        # Poignée de déplacement (Drag Handle)
        self.drag = QtWidgets.QLabel("⋮⋮", objectName="miniDrag")
        self.drag.installEventFilter(self)
        cv.addWidget(self.drag, 0, Qt.AlignLeft | Qt.AlignVCenter)

        # Cartes des personnages
        self.cards_row = QtWidgets.QHBoxLayout()
        self.cards_row.setContentsMargins(0, 0, 0, 0)
        self.cards_row.setSpacing(MINI_SPACING)
        cv.addLayout(self.cards_row, 1)

        # Séparateur vertical discret
        sep = QtWidgets.QFrame()
        sep.setFrameShape(QtWidgets.QFrame.VLine)
        sep.setStyleSheet("color: rgba(255, 255, 255, 0.15); max-height: 28px;")
        cv.addWidget(sep, 0, Qt.AlignVCenter)

        # Panneau de contrôle droit (Raccourci + PiP + Pin + Cadenas + Settings + Croix de retour)
        right_w = QtWidgets.QWidget()
        right_l = QtWidgets.QHBoxLayout(right_w)
        right_l.setContentsMargins(0, 0, 0, 0)
        right_l.setSpacing(4)

        # Badge / Bouton raccourci 'Suivant'
        self.btn_hk = QtWidgets.QPushButton(objectName="miniHkBtn")
        self.btn_hk.setFixedHeight(26)
        self.btn_hk.setToolTip("Raccourci Suivant (cliquer pour changer)")
        self.set_next_hotkey_label(getattr(self.main, "hotkey_next", ""))
        self.btn_hk.clicked.connect(self._change_next_hotkey)
        right_l.addWidget(self.btn_hk, 0, Qt.AlignVCenter)

        # Bouton PiP (Miniatures vidéo en direct)
        self.btn_pip = QtWidgets.QPushButton(objectName="miniPinBtn")
        self.btn_pip.setFixedSize(26, 26)
        self.btn_pip.setCheckable(True)
        self.btn_pip.setChecked(self.pip_enabled)
        self.btn_pip.setText("🖼️")
        self.btn_pip.setToolTip("Afficher / Masquer les miniatures vidéo en direct (PiP)")
        self.btn_pip.clicked.connect(self._toggle_pip)
        right_l.addWidget(self.btn_pip, 0, Qt.AlignVCenter)

        # Bouton Pin / Visibilité
        self.btn_pin = QtWidgets.QPushButton(objectName="miniPinBtn")
        self.btn_pin.setFixedSize(26, 26)
        self.btn_pin.setCheckable(True)
        self.btn_pin.setChecked(not self.hide_outside_dofus)
        self.btn_pin.setText("📌" if not self.hide_outside_dofus else "👁")
        self.btn_pin.setToolTip("Basculer la visibilité (Toujours visible / Auto-masquer)")
        self.btn_pin.clicked.connect(self._toggle_always_visible)
        right_l.addWidget(self.btn_pin, 0, Qt.AlignVCenter)

        # Bouton Cadenas (Figer / Verrouiller)
        self.btn_lock = QtWidgets.QPushButton(objectName="miniPinBtn")
        self.btn_lock.setFixedSize(26, 26)
        self.btn_lock.clicked.connect(self._toggle_lock)
        right_l.addWidget(self.btn_lock, 0, Qt.AlignVCenter)

        # Bouton Paramètres (Settings)
        self.btn_settings = QtWidgets.QPushButton(objectName="miniPinBtn")
        self.btn_settings.setFixedSize(26, 26)
        ico_set = load_icon("settings.svg")
        if not ico_set.isNull():
            self.btn_settings.setIcon(ico_set)
            self.btn_settings.setIconSize(QtCore.QSize(14, 14))
        else:
            self.btn_settings.setText("⚙")
        self.btn_settings.setToolTip("Ouvrir les Paramètres")
        self.btn_settings.clicked.connect(self._open_settings)
        right_l.addWidget(self.btn_settings, 0, Qt.AlignVCenter)

        # Bouton fermer / retour mode standard
        self.btn_close = QtWidgets.QPushButton("✕", objectName="miniCloseBare")
        self.btn_close.setFixedSize(26, 26)
        self.btn_close.setToolTip("Retourner au mode standard (Échap)")
        self.btn_close.clicked.connect(self._exit_to_main)
        right_l.addWidget(self.btn_close, 0, Qt.AlignVCenter)

        cv.addWidget(right_w, 0, Qt.AlignVCenter)
        root.addWidget(self.cont)

        self._card_widgets: list[MiniCardItem] = []
        self._populate_cards()

        self._update_lock_ui()

        self._drag_pos: QPoint | None = None
        self._auto_resize_and_position()

        # Timer de visibilité contextuelle et de détection de focus
        self._vis_timer = QTimer(self)
        self._vis_timer.setInterval(250)
        self._vis_timer.timeout.connect(self._visibility_tick)
        self._vis_timer.start()

    def _update_lock_ui(self):
        if self.is_locked:
            self.btn_lock.setText("🔒")
            self.btn_lock.setToolTip("Mini-Mode verrouillé (cliquer pour déverrouiller)")
            self.drag.setCursor(Qt.ArrowCursor)
            self.drag.setToolTip("Position verrouillée")
        else:
            self.btn_lock.setText("🔓")
            self.btn_lock.setToolTip("Verrouiller la position du Mini-Mode")
            self.drag.setCursor(Qt.OpenHandCursor)
            self.drag.setToolTip("Glisser pour déplacer")

    def _toggle_lock(self):
        if not self.is_locked:
            reply = QtWidgets.QMessageBox.question(
                self,
                "Verrouiller le Mini-Mode",
                "Voulez-vous verrouiller la position du Mini-Mode ?\nIl ne pourra plus être déplacé par mégarde à la souris.",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.Yes,
            )
            if reply == QtWidgets.QMessageBox.Yes:
                self.is_locked = True
                self.main.settings.setValue("mini/locked", True)
                self._update_lock_ui()
        else:
            self.is_locked = False
            self.main.settings.setValue("mini/locked", False)
            self._update_lock_ui()

    def _toggle_pip(self):
        """Bascule l'affichage des miniatures vidéo DWM PiP."""
        self.pip_enabled = not self.pip_enabled
        self.main.settings.setValue("mini/pip_enabled", self.pip_enabled)
        self.btn_pip.setChecked(self.pip_enabled)
        self._update_pip_state()

    def _update_pip_state(self):
        """Met à jour la hauteur du HUD et l'état PiP de chaque carte."""
        target_h = MINI_H_PIP if self.pip_enabled else MINI_H_COMPACT
        self.cont.setFixedHeight(target_h)
        for card in self._card_widgets:
            card.set_pip_enabled(self.pip_enabled)
        self._auto_resize_and_position(keep_center=False)

    def _on_card_hover_entered(self, card: MiniCardItem):
        """Affiche le popup d'aperçu agrandi en direct au survol si activé."""
        if not self.pip_hover_enabled or not card.handle or self.pip_enabled:
            return

        if self._hover_popup:
            try:
                self._hover_popup.close()
            except Exception:
                pass
            self._hover_popup = None

        self._hover_popup = DwmHoverPreviewPopup(
            card.pseudo,
            card.classe,
            card.handle,
            parent=None,
        )
        self._hover_popup.request_focus.connect(self._focus_handle)
        self._hover_popup.show_near_widget(card)

    def _on_card_hover_left(self, card: MiniCardItem):
        """Déclenche la fermeture douce de l'aperçu au survol."""
        if self._hover_popup:
            QTimer.singleShot(150, self._check_close_hover_popup)

    def _check_close_hover_popup(self):
        if self._hover_popup and not self._hover_popup.underMouse():
            try:
                self._hover_popup.close()
            except Exception:
                pass
            self._hover_popup = None

    def _open_settings(self):
        dlg = SettingsDialog(self)
        if dlg.exec() == QtWidgets.QDialog.Accepted:
            self.refresh_settings_from_app()

    def refresh_settings_from_app(self):
        """Met à jour l'opacité et les options en temps réel après modification des réglages."""
        self.hide_outside_dofus = bool(self.main.settings.value("mini/hide_outside", True, bool))
        self.always_on_top = bool(self.main.settings.value("mini/always_on_top", False, bool))
        self.btn_pin.setChecked(not self.hide_outside_dofus)
        self.btn_pin.setText("📌" if not self.hide_outside_dofus else "👁")

        self.pip_enabled = bool(self.main.settings.value("mini/pip_enabled", False, bool))
        self.pip_hover_enabled = bool(self.main.settings.value("mini/pip_hover_enabled", True, bool))
        self.btn_pip.setChecked(self.pip_enabled)
        self._update_pip_state()

        op = int(self.main.settings.value("mini/opacity", 90))
        self.setWindowOpacity(max(0.2, min(1.0, op / 100.0)))

    def _populate_cards(self):
        """Alimente les cartes de l'overlay HUD."""
        while self.cards_row.count():
            it = self.cards_row.takeAt(0)
            w = it.widget()
            if w:
                w.hide()
                w.setParent(None)
                w.deleteLater()
        self._card_widgets = []

        seen_handles = set()
        for i, w in enumerate(self.windows[:8]):
            h = w.get("handle", 0)
            if h and h in seen_handles:
                continue
            if h:
                seen_handles.add(h)

            card = MiniCardItem(
                index=len(self._card_widgets),
                pseudo=w.get("pseudo", ""),
                classe=w.get("classe", ""),
                handle=h,
                enabled=bool(w.get("enabled", True)),
            )
            card.toggled.connect(self._on_toggle_enabled)
            card.request_focus.connect(self._focus_handle)
            card.hover_entered.connect(self._on_card_hover_entered)
            card.hover_left.connect(self._on_card_hover_left)
            card.set_pip_enabled(self.pip_enabled)
            self.cards_row.addWidget(card)
            self._card_widgets.append(card)

        # Définir le premier comme actif par défaut
        if self._card_widgets:
            self.set_active_handle(self._card_widgets[0].handle)

    def remove_handle(self, handle: int):
        """Supprime une carte lorsque sa fenêtre Dofus a été fermée."""
        self.windows = [w for w in self.windows if w.get("handle") != handle]
        self._populate_cards()
        self._auto_resize_and_position(keep_center=False)

    def set_active_handle(self, hwnd: int):
        """Met en avant visuellement la carte du personnage correspondant au handle hwnd."""
        self._active_handle = hwnd
        for card in self._card_widgets:
            card.set_active(card.handle == hwnd)

    def reorder_from_main(self, handles_order: list[int]):
        """Réordonne les cartes du mini-mode selon l'ordre de la liste principale."""
        handle_to_card = {getattr(c, "handle", None): c for c in self._card_widgets}
        new_cards = []
        seen = set()
        for h in handles_order:
            if h in handle_to_card and h not in seen:
                seen.add(h)
                new_cards.append(handle_to_card[h])
        for c in self._card_widgets:
            if c not in new_cards:
                new_cards.append(c)

        while self.cards_row.count():
            self.cards_row.takeAt(0)
        for i, c in enumerate(new_cards):
            c.set_index(i)
            c.set_pip_enabled(self.pip_enabled)
            self.cards_row.addWidget(c)
        self._card_widgets = new_cards
        self._auto_resize_and_position(keep_center=False)

    def _auto_resize_and_position(self, keep_center: bool = True):
        """Ajuste la largeur et la hauteur de l'overlay et restaure sa position enregistrée."""
        n = max(1, len(self._card_widgets or self.windows[:8]))
        cards_total_w = (n * MINI_CARD_W) + ((n - 1) * MINI_SPACING)
        # drag (16) + cards + sep (10) + right_panel (~176 avec PiP) + paddings (8)
        total_w = DRAG_BAR_W + cards_total_w + 12 + 180 + (ROOT_PADDING * 2)
        total_h = MINI_H_PIP if self.pip_enabled else MINI_H_COMPACT

        self.setFixedSize(total_w, total_h)

        # Vérifier si une position sauvegardée existe
        pos_x = self.main.settings.value("mini/pos_x", None)
        pos_y = self.main.settings.value("mini/pos_y", None)

        pos_valid = False
        if pos_x is not None and pos_y is not None:
            try:
                x = int(pos_x)
                y = int(pos_y)
                # Vérifier que (x, y) est visible sur au moins un écran connecté
                for scr in QtGui.QGuiApplication.screens():
                    if scr.geometry().contains(QtCore.QPoint(x + 20, y + 20)):
                        pos_valid = True
                        self.move(x, y)
                        break
            except Exception:
                pos_valid = False

        if not pos_valid and keep_center:
            try:
                scr = QtGui.QGuiApplication.primaryScreen().availableGeometry()
                x = scr.x() + (scr.width() - total_w) // 2
                y = scr.y() + 10
                self.move(x, y)
            except Exception:
                pass

    def _save_position(self):
        try:
            p = self.pos()
            self.main.settings.setValue("mini/pos_x", p.x())
            self.main.settings.setValue("mini/pos_y", p.y())
        except Exception:
            pass

    def eventFilter(self, obj, event):
        """Gestion du drag-and-drop de l'overlay à la souris si non verrouillé."""
        if obj is self.drag:
            if self.is_locked:
                return super().eventFilter(obj, event)

            et = event.type()
            if et == QtCore.QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                self.drag.setCursor(Qt.ClosedHandCursor)
                return True
            if et == QtCore.QEvent.MouseMove and self._drag_pos is not None and (event.buttons() & Qt.LeftButton):
                self.move(event.globalPosition().toPoint() - self._drag_pos)
                self._save_position()
                return True
            if et == QtCore.QEvent.MouseButtonRelease:
                self._drag_pos = None
                self.drag.setCursor(Qt.OpenHandCursor)
                self._save_position()
                return True
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event: QtGui.QKeyEvent):
        if event.key() == Qt.Key_Escape:
            self._exit_to_main()
            event.accept()
            return
        super().keyPressEvent(event)

    def _on_toggle_enabled(self, handle: int, enabled: bool):
        try:
            self.main.set_focus_enabled_for_handle(handle, enabled)
        except Exception:
            pass

    def _focus_handle(self, hwnd: int):
        self.set_active_handle(hwnd)
        if hasattr(self.main, "sync_active_handle"):
            self.main.sync_active_handle(hwnd)
        delay = int(self.main.settings.value("win32/delay_ms", 20))
        force_foreground(hwnd, delay_ms=delay)

    def _change_next_hotkey(self):
        if hasattr(self.main, "_capture_global_next_hotkey"):
            self.main._capture_global_next_hotkey()
            self.set_next_hotkey_label(getattr(self.main, "hotkey_next", ""))

    def _toggle_always_visible(self):
        self.hide_outside_dofus = not self.btn_pin.isChecked()
        self.btn_pin.setText("📌" if not self.hide_outside_dofus else "👁")
        self.main.settings.setValue("mini/hide_outside", self.hide_outside_dofus)
        if not self.hide_outside_dofus:
            self.show()

    def _exit_to_main(self):
        """Ferme l'overlay et réaffiche la fenêtre principale."""
        self._save_position()
        try:
            self._vis_timer.stop()
        except Exception:
            pass
        if self._hover_popup:
            try:
                self._hover_popup.close()
            except Exception:
                pass
            self._hover_popup = None
        self.main._mini = None
        self.main.showNormal()
        self.main.raise_()
        self.main.activateWindow()
        self.close()

    def closeEvent(self, event: QtGui.QCloseEvent):
        self._save_position()
        try:
            self._vis_timer.stop()
        except Exception:
            pass
        if self._hover_popup:
            try:
                self._hover_popup.close()
            except Exception:
                pass
            self._hover_popup = None
        if hasattr(self.main, "_mini") and self.main._mini is self:
            self.main._mini = None
        super().closeEvent(event)

    def set_next_hotkey_label(self, txt: str):
        display = format_hotkey_display(txt) or "Hotkey"
        self.btn_hk.setText(display)

    def _visibility_tick(self):
        """Vérifie périodiquement si Dofus a le focus pour masquer/afficher l'overlay et mettre à jour l'actif."""
        try:
            fg = win32gui.GetForegroundWindow()
        except Exception:
            fg = None

        if fg:
            try:
                root_hwnd = win32gui.GetAncestor(fg, win32con.GA_ROOT)
            except Exception:
                root_hwnd = fg

            # Synchronisation automatique de la carte active si l'utilisateur clique directement sur un Dofus
            for card in self._card_widgets:
                if card.handle and (card.handle == fg or card.handle == root_hwnd):
                    self.set_active_handle(card.handle)
                    if hasattr(self.main, "sync_active_handle"):
                        self.main.sync_active_handle(card.handle)
                    break

        if not self.hide_outside_dofus or self.always_on_top:
            self.show()
            return

        if time.monotonic() - self._opened_at < 1.0 or self._drag_pos is not None:
            self.show()
            return

        if not fg:
            self.show()
            return

        hwnd_self = int(self.winId())
        dofus_handles = [w.get("handle") for w in self.windows if w.get("handle")]

        is_allowed = (
            (root_hwnd == hwnd_self)
            or (root_hwnd in dofus_handles)
            or (fg in dofus_handles)
        )

        if is_allowed:
            self.show()
        else:
            self.hide()
