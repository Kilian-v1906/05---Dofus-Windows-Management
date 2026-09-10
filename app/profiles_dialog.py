"""
app/profiles_dialog.py
Gestionnaire complet de profils d'équipes Dofus (création, édition, réordonnancement, suppression).
"""

from PySide6 import QtWidgets, QtGui, QtCore
from PySide6.QtCore import Qt, QSize, Signal

from core.profiles import (
    get_profiles_list,
    load_profile,
    save_profile,
    delete_profile,
    rename_profile,
    is_profile_primary,
    set_profile_primary,
    open_profiles_directory,
    _signature_from_windows,
)
from core.window_manager import get_dofus_windows
from utils.hotkeys import normalize_hotkey_string, format_hotkey_display
from utils.paths import load_icon, icon_for_class



from app.hotkey_dialog import HotkeyCaptureDialog


class ProfileWinItemWidget(QtWidgets.QWidget):
    """Ligne représentant un personnage dans l'éditeur de profil."""

    toggled = Signal(bool)

    def __init__(self, index: int, pseudo: str, classe: str, enabled: bool = True, parent=None):
        super().__init__(parent)
        self.pseudo = pseudo
        self.classe = classe
        self.enabled = bool(enabled)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(8, 4, 8, 4)
        lay.setSpacing(10)

        # Interrupteur
        self.chk = QtWidgets.QCheckBox()
        self.chk.setChecked(self.enabled)
        self.chk.stateChanged.connect(lambda s: self.toggled.emit(bool(s)))

        # Icône de classe
        self.icon_lbl = QtWidgets.QLabel()
        pm = QtGui.QPixmap(icon_for_class(self.classe))
        if not pm.isNull():
            pm = pm.scaled(30, 30, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.icon_lbl.setPixmap(pm)
        self.icon_lbl.setFixedSize(30, 30)
        self.icon_lbl.setAlignment(Qt.AlignCenter)

        # Pseudo & Classe
        name_box = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(name_box)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(1)
        self.lbl_name = QtWidgets.QLabel(self.pseudo)
        self.lbl_name.setStyleSheet("font-size:13px; font-weight:600;")
        self.lbl_class = QtWidgets.QLabel(self.classe)
        self.lbl_class.setProperty("muted", True)
        v.addWidget(self.lbl_name)
        v.addWidget(self.lbl_class)

        # Badge index
        self.idx = QtWidgets.QLabel(f"#{index+1}")
        self.idx.setObjectName("indexBadge")

        lay.addWidget(self.chk)
        lay.addWidget(self.icon_lbl)
        lay.addWidget(name_box, 1)
        lay.addWidget(self.idx)

    def set_index(self, i: int):
        self.idx.setText(f"#{i+1}")


class ProfilesManagerDialog(QtWidgets.QDialog):
    """Dialogue modal de gestion des profils multi-comptes."""

    def __init__(self, main_window: QtWidgets.QWidget):
        super().__init__(main_window)
        self.main = main_window
        self.setWindowTitle("Gestion des profils d'équipe")
        ico = load_icon("dwm.ico")
        if not ico.isNull():
            self.setWindowIcon(ico)
        self.setModal(True)
        self.setMinimumSize(820, 620)
        self.resize(840, 640)

        self.profile_next_hotkey: str = ""
        self.profile_prev_hotkey: str = ""

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(12)

        # Barre d'actions supérieure
        actions = QtWidgets.QHBoxLayout()
        self.btn_new_from_open = QtWidgets.QPushButton("Nouveau depuis le jeu")
        self.btn_new_from_open.setIcon(load_icon("add.svg"))
        self.btn_new_from_open.setProperty("neon", "primary")

        self.btn_rename = QtWidgets.QPushButton("Renommer")
        self.btn_delete = QtWidgets.QPushButton("Supprimer")
        self.btn_toggle_primary = QtWidgets.QPushButton("★ Définir comme Principal")

        actions.addWidget(self.btn_new_from_open)
        actions.addWidget(self.btn_rename)
        actions.addWidget(self.btn_delete)
        actions.addStretch()
        actions.addWidget(self.btn_toggle_primary)
        root.addLayout(actions)

        # Corps principal (Liste des profils à gauche / Personnages du profil à droite)
        body = QtWidgets.QHBoxLayout()
        body.setSpacing(12)

        # Panneau gauche
        left_panel = QtWidgets.QFrame()
        left_panel.setObjectName("panelCard")
        left_l = QtWidgets.QVBoxLayout(left_panel)
        left_l.setContentsMargins(8, 8, 8, 8)
        left_l.setSpacing(6)

        lbl_profiles_title = QtWidgets.QLabel("Profils enregistrés :")
        lbl_profiles_title.setStyleSheet("font-weight:700; font-size:13px;")
        left_l.addWidget(lbl_profiles_title)

        self.profiles_list = QtWidgets.QListWidget()
        left_l.addWidget(self.profiles_list, 1)

        self.btn_open_folder = QtWidgets.QPushButton("Ouvrir dossier des profils")
        self.btn_open_folder.setToolTip("Ouvre le dossier contenant les fichiers JSON des profils dans l'Explorateur Windows")
        self.btn_open_folder.clicked.connect(open_profiles_directory)
        left_l.addWidget(self.btn_open_folder)


        # Panneau droit
        right_panel = QtWidgets.QFrame()
        right_panel.setObjectName("panelCard")
        right_l = QtWidgets.QVBoxLayout(right_panel)
        right_l.setContentsMargins(8, 8, 8, 8)
        right_l.setSpacing(8)

        lbl_chars_title = QtWidgets.QLabel("Ordre des personnages (Glisser-déposer pour réordonner) :")
        lbl_chars_title.setStyleSheet("font-weight:700; font-size:13px;")
        right_l.addWidget(lbl_chars_title)

        self.windows_list = QtWidgets.QListWidget()
        self.windows_list.setDragDropMode(QtWidgets.QAbstractItemView.InternalMove)
        self.windows_list.model().rowsMoved.connect(self._update_indexes_after_drag)
        right_l.addWidget(self.windows_list, 1)

        # Raccourcis du profil (Suivant et Précédent)
        hk_box = QtWidgets.QWidget()
        hk_lay = QtWidgets.QVBoxLayout(hk_box)
        hk_lay.setContentsMargins(0, 4, 0, 4)
        hk_lay.setSpacing(6)

        # Ligne Suivant
        hk_row1 = QtWidgets.QHBoxLayout()
        hk_row1.setSpacing(8)
        lbl_s = QtWidgets.QLabel("Raccourci Suivant :")
        lbl_s.setFixedWidth(130)
        self.btn_set_profile_next = QtWidgets.QPushButton("Définir...")
        self.btn_set_profile_next.setFixedHeight(28)
        self.btn_set_profile_next.clicked.connect(self._capture_profile_next_hotkey)
        self.btn_clear_profile_next = QtWidgets.QPushButton("✕")
        self.btn_clear_profile_next.setFixedSize(28, 28)
        self.btn_clear_profile_next.setToolTip("Effacer le raccourci Suivant")
        self.btn_clear_profile_next.clicked.connect(self._clear_profile_next_hotkey)

        self.lbl_profile_next = QtWidgets.QLabel("")
        self.lbl_profile_next.setObjectName("profileHotkeyBadge")
        self.lbl_profile_next.setMinimumWidth(70)
        self.lbl_profile_next.setAlignment(Qt.AlignCenter)

        hk_row1.addWidget(lbl_s)
        hk_row1.addWidget(self.btn_set_profile_next)
        hk_row1.addWidget(self.btn_clear_profile_next)
        hk_row1.addWidget(self.lbl_profile_next)
        hk_row1.addStretch()
        hk_lay.addLayout(hk_row1)

        # Ligne Précédent
        hk_row2 = QtWidgets.QHBoxLayout()
        hk_row2.setSpacing(8)
        lbl_p = QtWidgets.QLabel("Raccourci Précédent :")
        lbl_p.setFixedWidth(130)
        self.btn_set_profile_prev = QtWidgets.QPushButton("Définir...")
        self.btn_set_profile_prev.setFixedHeight(28)
        self.btn_set_profile_prev.clicked.connect(self._capture_profile_prev_hotkey)
        self.btn_clear_profile_prev = QtWidgets.QPushButton("✕")
        self.btn_clear_profile_prev.setFixedSize(28, 28)
        self.btn_clear_profile_prev.setToolTip("Effacer le raccourci Précédent")
        self.btn_clear_profile_prev.clicked.connect(self._clear_profile_prev_hotkey)

        self.lbl_profile_prev = QtWidgets.QLabel("")
        self.lbl_profile_prev.setObjectName("profileHotkeyBadge")
        self.lbl_profile_prev.setMinimumWidth(70)
        self.lbl_profile_prev.setAlignment(Qt.AlignCenter)

        hk_row2.addWidget(lbl_p)
        hk_row2.addWidget(self.btn_set_profile_prev)
        hk_row2.addWidget(self.btn_clear_profile_prev)
        hk_row2.addWidget(self.lbl_profile_prev)
        hk_row2.addStretch()
        hk_lay.addLayout(hk_row2)

        right_l.addWidget(hk_box)

        body.addWidget(left_panel, 1)
        body.addWidget(right_panel, 2)
        root.addLayout(body)

        # Barre inférieure
        bottom = QtWidgets.QHBoxLayout()
        self.btn_delete_char = QtWidgets.QPushButton("Supprimer personnage")
        bottom.addWidget(self.btn_delete_char)
        bottom.addStretch()

        self.btn_load_into_main = QtWidgets.QPushButton("Charger dans l'application")
        self.btn_save_profile = QtWidgets.QPushButton("Enregistrer")
        self.btn_save_profile.setProperty("neon", "success")

        bottom.addWidget(self.btn_load_into_main)
        bottom.addWidget(self.btn_save_profile)
        root.addLayout(bottom)

        # Connexions
        self.profiles_list.currentTextChanged.connect(self._on_profile_selected)
        self.btn_new_from_open.clicked.connect(self._new_from_open_windows)
        self.btn_rename.clicked.connect(self._rename_profile)
        self.btn_delete.clicked.connect(self._delete_profile)
        self.btn_toggle_primary.clicked.connect(self._toggle_primary)
        self.btn_delete_char.clicked.connect(self._delete_selected_char)
        self.btn_load_into_main.clicked.connect(self._load_into_main)
        self.btn_save_profile.clicked.connect(self._save_current_profile)

        self._reload_profiles()

    def _clean_name(self, display_text: str) -> str:
        """Nettoie le nom de profil en retirant l'étoile ★ éventuelle."""
        txt = display_text.strip()
        if txt.startswith("★ "):
            return txt[2:].strip()
        return txt

    def _current_profile_name(self) -> str:
        it = self.profiles_list.currentItem()
        return self._clean_name(it.text()) if it else ""

    def _reload_profiles(self, select_name: str = ""):
        """Recharge la liste des profils avec indicateur de profil principal."""
        self.profiles_list.clear()
        target_item = None
        for name in get_profiles_list():
            is_prim = is_profile_primary(name)
            display = f"★ {name}" if is_prim else name
            it = QtWidgets.QListWidgetItem(display)
            it.setData(Qt.UserRole, name)
            self.profiles_list.addItem(it)
            if select_name and name.lower() == select_name.lower():
                target_item = it

        if target_item:
            self.profiles_list.setCurrentItem(target_item)
        elif self.profiles_list.count() > 0:
            self.profiles_list.setCurrentRow(0)

    def _on_profile_selected(self, _):
        """Met à jour l'éditeur lorsque l'utilisateur sélectionne un profil."""
        self.windows_list.clear()
        self.profile_next_hotkey = ""
        self.profile_prev_hotkey = ""
        self.lbl_profile_next.setText("")
        self.lbl_profile_prev.setText("")

        name = self._current_profile_name()
        if not name:
            return

        data = load_profile(name) or {}
        ghk = data.get("global_hotkeys") or {}

        hk_next = ghk.get("next", "")
        if hk_next:
            self.profile_next_hotkey = normalize_hotkey_string(hk_next)
            self.lbl_profile_next.setText(format_hotkey_display(self.profile_next_hotkey))

        hk_prev = ghk.get("prev", "")
        if hk_prev:
            self.profile_prev_hotkey = normalize_hotkey_string(hk_prev)
            self.lbl_profile_prev.setText(format_hotkey_display(self.profile_prev_hotkey))

        wins = data.get("windows", [])
        for i, w in enumerate(wins):
            pseudo = str(w.get("pseudo", "")).strip()
            classe = str(w.get("classe", "")).strip()
            enabled = bool(w.get("enabled", True))

            it = QtWidgets.QListWidgetItem()
            it.setData(Qt.UserRole, {"pseudo": pseudo, "classe": classe, "enabled": enabled})
            it.setSizeHint(QSize(0, 48))

            row_widget = ProfileWinItemWidget(i, pseudo, classe, enabled)
            row_widget.toggled.connect(lambda s, item=it: self._on_row_toggled(item, s))

            self.windows_list.addItem(it)
            self.windows_list.setItemWidget(it, row_widget)

    def _on_row_toggled(self, item: QtWidgets.QListWidgetItem, enabled: bool):
        d = item.data(Qt.UserRole) or {}
        d["enabled"] = bool(enabled)
        item.setData(Qt.UserRole, d)

    def _update_indexes_after_drag(self):
        for i in range(self.windows_list.count()):
            it = self.windows_list.item(i)
            w = self.windows_list.itemWidget(it)
            if isinstance(w, ProfileWinItemWidget):
                w.set_index(i)

    def _current_windows_array(self) -> list[dict]:
        arr = []
        for i in range(self.windows_list.count()):
            it = self.windows_list.item(i)
            d = it.data(Qt.UserRole) or {}
            arr.append({
                "pseudo": str(d.get("pseudo", "")).strip(),
                "classe": str(d.get("classe", "")).strip(),
                "enabled": bool(d.get("enabled", True)),
            })
        return arr

    def _save_current_profile(self):
        name = self._current_profile_name()
        if not name:
            QtWidgets.QMessageBox.warning(self, "Profil", "Veuillez sélectionner un profil.")
            return

        windows = self._current_windows_array()
        extra = {"global_hotkeys": {}}
        if self.profile_next_hotkey:
            extra["global_hotkeys"]["next"] = self.profile_next_hotkey
        if self.profile_prev_hotkey:
            extra["global_hotkeys"]["prev"] = self.profile_prev_hotkey

        if save_profile(name, windows, extra=extra):
            QtWidgets.QMessageBox.information(self, "Profil", f"Le profil '{name}' a été enregistré.")
        else:
            QtWidgets.QMessageBox.critical(self, "Erreur", f"Échec de l'enregistrement du profil '{name}'.")

    def _new_from_open_windows(self):
        detected = get_dofus_windows()
        if not detected:
            QtWidgets.QMessageBox.information(
                self, "Nouveau profil",
                "Aucune fenêtre Dofus n'a été détectée actuellement.\nLancez d'abord vos comptes de jeu."
            )
            return

        name, ok = QtWidgets.QInputDialog.getText(
            self, "Nouveau profil", "Entrez le nom de l'équipe / profil :"
        )
        if not ok or not name.strip():
            return
        name = name.strip()

        if name in get_profiles_list():
            QtWidgets.QMessageBox.warning(self, "Profil", "Un profil avec ce nom existe déjà.")
            return

        windows = [{"pseudo": w["pseudo"], "classe": w["classe"], "enabled": True} for w in detected]
        if save_profile(name, windows):
            self._reload_profiles(select_name=name)
        else:
            QtWidgets.QMessageBox.critical(self, "Erreur", "Impossible de créer le profil.")

    def _rename_profile(self):
        old_name = self._current_profile_name()
        if not old_name:
            return

        new_name, ok = QtWidgets.QInputDialog.getText(
            self, "Renommer", f"Nouveau nom pour '{old_name}' :"
        )
        if not ok or not new_name.strip():
            return
        new_name = new_name.strip()

        if new_name == old_name:
            return

        if new_name in get_profiles_list():
            QtWidgets.QMessageBox.warning(self, "Profil", "Un profil avec ce nom existe déjà.")
            return

        if rename_profile(old_name, new_name):
            self._reload_profiles(select_name=new_name)
        else:
            QtWidgets.QMessageBox.critical(self, "Erreur", "Impossible de renommer le profil.")

    def _delete_profile(self):
        name = self._current_profile_name()
        if not name:
            return

        reply = QtWidgets.QMessageBox.question(
            self, "Supprimer",
            f"Êtes-vous sûr de vouloir supprimer définitivement le profil '{name}' ?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No
        )
        if reply == QtWidgets.QMessageBox.Yes:
            delete_profile(name)
            self._reload_profiles()

    def _toggle_primary(self):
        name = self._current_profile_name()
        if not name:
            return
        current_status = is_profile_primary(name)
        set_profile_primary(name, not current_status)
        self._reload_profiles(select_name=name)

    def _delete_selected_char(self):
        r = self.windows_list.currentRow()
        if r >= 0:
            self.windows_list.takeItem(r)
            self._update_indexes_after_drag()

    def _capture_profile_next_hotkey(self):
        dlg = HotkeyCaptureDialog(
            "Raccourci 'Suivant' du profil",
            self,
            current_hotkey=self.profile_next_hotkey
        )
        dlg.hotkey_selected.connect(self._on_profile_next_hotkey_selected)
        dlg.exec()

    def _on_profile_next_hotkey_selected(self, hk: str):
        self.profile_next_hotkey = hk
        self.lbl_profile_next.setText(format_hotkey_display(hk))

    def _clear_profile_next_hotkey(self):
        self.profile_next_hotkey = ""
        self.lbl_profile_next.setText("")

    def _capture_profile_prev_hotkey(self):
        dlg = HotkeyCaptureDialog(
            "Raccourci 'Précédent' du profil",
            self,
            current_hotkey=self.profile_prev_hotkey
        )
        dlg.hotkey_selected.connect(self._on_profile_prev_hotkey_selected)
        dlg.exec()

    def _on_profile_prev_hotkey_selected(self, hk: str):
        self.profile_prev_hotkey = hk
        self.lbl_profile_prev.setText(format_hotkey_display(hk))

    def _clear_profile_prev_hotkey(self):
        self.profile_prev_hotkey = ""
        self.lbl_profile_prev.setText("")

    def _load_into_main(self):
        name = self._current_profile_name()
        if not name:
            return

        data = load_profile(name) or {}
        wins = data.get("windows", [])
        if hasattr(self.main, "_populate_list_from_windows"):
            self.main._populate_list_from_windows(wins)
            self.main._recompute_internal_order()
            self.main._adjust_height_to_list()

        ghk = data.get("global_hotkeys") or {}
        hk_next = ghk.get("next")
        if hk_next and hasattr(self.main, "set_next_hotkey"):
            self.main.set_next_hotkey(hk_next)

        hk_prev = ghk.get("prev")
        if hk_prev and hasattr(self.main, "set_prev_hotkey"):
            self.main.set_prev_hotkey(hk_prev)

        self.accept()
