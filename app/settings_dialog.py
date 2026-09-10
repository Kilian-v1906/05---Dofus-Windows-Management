"""
app/settings_dialog.py
Boîte de dialogue de configuration de l'application.
"""

from PySide6 import QtWidgets, QtGui, QtCore
from PySide6.QtCore import Qt
from utils.paths import get_app_settings, load_icon, apply_theme_to_app
from utils.hotkeys import format_hotkey_display, normalize_hotkey_string
from core.updater import APP_VERSION, UpdateCheckerWorker
from app.update_dialog import UpdateDialog



class SettingsDialog(QtWidgets.QDialog):
    """Dialogue de réglages avancés (Thème, Délais Win32, Mini-mode, Raccourcis)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Paramètres")
        ico = load_icon("dwm.ico")
        if not ico.isNull():
            self.setWindowIcon(ico)
        self.setMinimumWidth(480)
        self.setModal(True)

        self.settings = get_app_settings()

        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(18, 18, 18, 18)
        v.setSpacing(14)

        # Groupe Mini-Mode
        grp_mini = QtWidgets.QGroupBox("Mini-Mode (Overlay en jeu)")
        grp_mini_lay = QtWidgets.QVBoxLayout(grp_mini)
        grp_mini_lay.setSpacing(10)

        self.chk_hide_outside = QtWidgets.QCheckBox("Masquer automatiquement quand Dofus n'est pas actif")
        self.chk_always_on_top = QtWidgets.QCheckBox("Toujours afficher au premier plan (forcer la visibilité)")
        self.chk_pip = QtWidgets.QCheckBox("Activer les miniatures vidéo en direct (PiP) sous chaque carte")
        self.chk_pip_hover = QtWidgets.QCheckBox("Afficher un aperçu agrandi au survol d'une carte")

        row_opacity = QtWidgets.QHBoxLayout()
        row_opacity.addWidget(QtWidgets.QLabel("Opacité du Mini-Mode :"))
        self.slider_opacity = QtWidgets.QSlider(Qt.Horizontal)
        self.slider_opacity.setRange(20, 100)
        self.slider_opacity.setSingleStep(5)
        self.lbl_opacity_val = QtWidgets.QLabel("90%")
        self.lbl_opacity_val.setFixedWidth(42)
        self.lbl_opacity_val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.lbl_opacity_val.setStyleSheet("font-weight:600;")
        self.slider_opacity.valueChanged.connect(lambda v: self.lbl_opacity_val.setText(f"{v}%"))

        row_opacity.addWidget(self.slider_opacity)
        row_opacity.addWidget(self.lbl_opacity_val)

        grp_mini_lay.addWidget(self.chk_hide_outside)
        grp_mini_lay.addWidget(self.chk_always_on_top)
        grp_mini_lay.addWidget(self.chk_pip)
        grp_mini_lay.addWidget(self.chk_pip_hover)
        grp_mini_lay.addLayout(row_opacity)
        v.addWidget(grp_mini)

        # Groupe Système & Focus Win32
        grp_sys = QtWidgets.QGroupBox("Système & Focus Win32")
        grp_sys_lay = QtWidgets.QVBoxLayout(grp_sys)
        grp_sys_lay.setSpacing(8)

        row_delay = QtWidgets.QHBoxLayout()
        row_delay.addWidget(QtWidgets.QLabel("Délai d'activation Win32 :"))
        self.spin_delay = QtWidgets.QSpinBox()
        self.spin_delay.setRange(0, 300)
        self.spin_delay.setSingleStep(5)
        self.spin_delay.setSuffix(" ms")
        row_delay.addWidget(self.spin_delay)
        grp_sys_lay.addLayout(row_delay)

        info_delay = QtWidgets.QLabel(
            "Temps d'attente lors de la restauration d'une fenêtre. Augmentez à 20-50 ms si le focus saute."
        )
        info_delay.setProperty("muted", True)
        info_delay.setWordWrap(True)
        grp_sys_lay.addWidget(info_delay)
        v.addWidget(grp_sys)

        # Groupe Profils d'équipe (Détection automatique)
        grp_prof = QtWidgets.QGroupBox("Profils d'équipe")
        grp_prof_lay = QtWidgets.QVBoxLayout(grp_prof)
        grp_prof_lay.setSpacing(8)

        self.chk_auto_detect = QtWidgets.QCheckBox("Activer la détection automatique du profil")
        grp_prof_lay.addWidget(self.chk_auto_detect)

        info_prof = QtWidgets.QLabel(
            "Associe automatiquement les comptes Dofus ouverts au profil d'équipe correspondant "
            "et affiche le profil sélectionné dans l'en-tête."
        )
        info_prof.setProperty("muted", True)
        info_prof.setWordWrap(True)
        grp_prof_lay.addWidget(info_prof)
        v.addWidget(grp_prof)

        # Groupe Apparence
        grp_ui = QtWidgets.QGroupBox("Apparence")
        grp_ui_lay = QtWidgets.QHBoxLayout(grp_ui)
        grp_ui_lay.addWidget(QtWidgets.QLabel("Thème de l'interface :"))
        self.combo_theme = QtWidgets.QComboBox()
        self.THEME_OPTIONS = [
            ("Sombre (Gamer Dark)", "dark"),
            ("Clair (Gamer Light)", "light"),
            ("Doré (Or & Ambre)", "gold"),
            ("Rouge (Crimson)", "red"),
            ("Vert (Émeraude)", "green"),
            ("Bleu (Cobalt)", "blue"),
        ]
        for label, key in self.THEME_OPTIONS:
            self.combo_theme.addItem(label, userData=key)
        grp_ui_lay.addWidget(self.combo_theme)
        v.addWidget(grp_ui)

        # Groupe Mises à jour
        grp_upd = QtWidgets.QGroupBox("Mises à jour")
        grp_upd_lay = QtWidgets.QVBoxLayout(grp_upd)
        grp_upd_lay.setSpacing(8)

        row_v = QtWidgets.QHBoxLayout()
        lbl_v = QtWidgets.QLabel(f"Version installée : <b>v{APP_VERSION}</b>")
        self.btn_check_update = QtWidgets.QPushButton("Rechercher les mises à jour")
        self.btn_check_update.clicked.connect(self._check_for_updates)
        row_v.addWidget(lbl_v)
        row_v.addStretch()
        row_v.addWidget(self.btn_check_update)
        grp_upd_lay.addLayout(row_v)

        self.chk_auto_update = QtWidgets.QCheckBox("Vérifier automatiquement les mises à jour au démarrage")
        grp_upd_lay.addWidget(self.chk_auto_update)
        v.addWidget(grp_upd)


        # Boutons d'action
        v.addSpacing(6)
        btn_row = QtWidgets.QHBoxLayout()
        btn_cancel = QtWidgets.QPushButton("Annuler")
        btn_cancel.clicked.connect(self.reject)

        btn_save = QtWidgets.QPushButton("Enregistrer")
        btn_save.setProperty("neon", "primary")
        btn_save.clicked.connect(self.accept)

        btn_row.addStretch()
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_save)
        v.addLayout(btn_row)

        self._load_values()

    def _load_values(self):
        """Charge les valeurs depuis QSettings."""
        self.chk_always_on_top.setChecked(self.settings.value("mini/always_on_top", False, bool))
        self.chk_hide_outside.setChecked(self.settings.value("mini/hide_outside", True, bool))
        self.chk_pip.setChecked(self.settings.value("mini/pip_enabled", False, bool))
        self.chk_pip_hover.setChecked(self.settings.value("mini/pip_hover_enabled", True, bool))
        self.spin_delay.setValue(int(self.settings.value("win32/delay_ms", 20)))

        # Profil automatique (par défaut activé)
        self.chk_auto_detect.setChecked(self.settings.value("profiles/auto_detect_enabled", True, bool))

        # Mises à jour automatiques au démarrage (par défaut activé)
        self.chk_auto_update.setChecked(self.settings.value("updates/check_on_startup", True, bool))

        op = int(self.settings.value("mini/opacity", 90))
        self.slider_opacity.setValue(op)
        self.lbl_opacity_val.setText(f"{op}%")

        theme = str(self.settings.value("ui/theme", "dark")).lower()
        idx_found = 0
        for i, (_, key) in enumerate(self.THEME_OPTIONS):
            if key == theme:
                idx_found = i
                break
        self.combo_theme.setCurrentIndex(idx_found)

    def _check_for_updates(self):
        """Lance une vérification manuelle de mise à jour."""
        self.btn_check_update.setEnabled(False)
        self.btn_check_update.setText("Recherche...")

        self.worker = UpdateCheckerWorker(self)

        def on_finished(res: dict):
            self.btn_check_update.setEnabled(True)
            self.btn_check_update.setText("Rechercher les mises à jour")
            if res.get("update_available"):
                dlg = UpdateDialog(res, self)
                dlg.exec()
            else:
                QtWidgets.QMessageBox.information(
                    self,
                    "Mises à jour",
                    f"Votre application Dofus Organizer est à jour (v{APP_VERSION})."
                )

        def on_failed(msg: str):
            self.btn_check_update.setEnabled(True)
            self.btn_check_update.setText("Rechercher les mises à jour")
            QtWidgets.QMessageBox.warning(self, "Mises à jour", msg)

        self.worker.check_finished.connect(on_finished)
        self.worker.check_failed.connect(on_failed)
        self.worker.start()

    def accept(self):
        """Enregistre les valeurs dans QSettings et applique le thème."""
        self.settings.setValue("mini/always_on_top", self.chk_always_on_top.isChecked())
        self.settings.setValue("mini/hide_outside", self.chk_hide_outside.isChecked())
        self.settings.setValue("mini/pip_enabled", self.chk_pip.isChecked())
        self.settings.setValue("mini/pip_hover_enabled", self.chk_pip_hover.isChecked())
        self.settings.setValue("mini/opacity", self.slider_opacity.value())
        self.settings.setValue("win32/delay_ms", self.spin_delay.value())

        self.settings.setValue("profiles/auto_detect_enabled", self.chk_auto_detect.isChecked())
        self.settings.setValue("updates/check_on_startup", self.chk_auto_update.isChecked())

        theme_key = self.combo_theme.currentData() or "dark"
        self.settings.setValue("ui/theme", theme_key)

        apply_theme_to_app(QtWidgets.QApplication.instance(), theme_key)
        super().accept()

