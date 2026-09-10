"""
app/update_dialog.py
Boîte de dialogue de mise à jour avec affichage des notes de version (changelog)
et barre de progression de téléchargement.
"""

from PySide6 import QtWidgets, QtGui, QtCore
from PySide6.QtCore import Qt
from utils.paths import load_icon
from core.updater import UpdateDownloaderWorker, launch_installer_and_exit


class UpdateDialog(QtWidgets.QDialog):
    """Dialogue de proposition et téléchargement de mise à jour."""

    def __init__(self, update_info: dict, parent=None):
        super().__init__(parent)
        self.update_info = update_info
        self.downloader: UpdateDownloaderWorker | None = None

        self.setWindowTitle("Mise à jour disponible")
        ico = load_icon("dwm.ico")
        if not ico.isNull():
            self.setWindowIcon(ico)
        self.setModal(True)
        self.resize(520, 420)

        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(20, 20, 20, 20)
        v.setSpacing(14)

        # En-tête
        head_box = QtWidgets.QHBoxLayout()
        head_box.setSpacing(14)

        ico_lbl = QtWidgets.QLabel()
        if not ico.isNull():
            ico_lbl.setPixmap(ico.pixmap(48, 48))
        ico_lbl.setFixedSize(48, 48)
        head_box.addWidget(ico_lbl)

        head_text = QtWidgets.QVBoxLayout()
        head_text.setSpacing(2)

        curr = self.update_info.get("current_version", "")
        latest = self.update_info.get("latest_version", "")

        t_title = QtWidgets.QLabel("Nouvelle mise à jour disponible !")
        t_title.setStyleSheet("font-size: 16px; font-weight: 700; color: #4FC3F7;")
        t_sub = QtWidgets.QLabel(f"Version actuelle : <b>v{curr}</b>  ➔  Nouvelle version : <b style='color:#00E676;'>v{latest}</b>")
        t_sub.setStyleSheet("font-size: 13px;")

        head_text.addWidget(t_title)
        head_text.addWidget(t_sub)
        head_box.addLayout(head_text, 1)
        v.addLayout(head_box)

        # Notes de version (Changelog)
        lbl_notes = QtWidgets.QLabel("Nouveautés & Modifications :")
        lbl_notes.setStyleSheet("font-weight: 600; font-size: 12px;")
        v.addWidget(lbl_notes)

        self.txt_notes = QtWidgets.QTextBrowser()
        self.txt_notes.setOpenExternalLinks(True)
        notes = self.update_info.get("release_notes", "") or "Aucune note de version détaillée pour cette mise à jour."
        self.txt_notes.setMarkdown(notes)
        self.txt_notes.setStyleSheet("background: rgba(0,0,0,0.25); border-radius: 6px; padding: 8px;")
        v.addWidget(self.txt_notes, 1)

        # Section Téléchargement & Progression
        self.prog_box = QtWidgets.QWidget()
        self.prog_lay = QtWidgets.QVBoxLayout(self.prog_box)
        self.prog_lay.setContentsMargins(0, 0, 0, 0)
        self.prog_lay.setSpacing(6)

        self.lbl_status = QtWidgets.QLabel("Cliquez sur « Mettre à jour » pour démarrer l'installation.")
        self.lbl_status.setStyleSheet("font-size: 11px; color: #A0A5B5;")

        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFixedHeight(18)
        self.prog_box.setVisible(False)

        self.prog_lay.addWidget(self.lbl_status)
        self.prog_lay.addWidget(self.progress_bar)
        v.addWidget(self.prog_box)

        # Boutons
        btn_row = QtWidgets.QHBoxLayout()
        self.btn_later = QtWidgets.QPushButton("Plus tard")
        self.btn_later.clicked.connect(self._on_later_or_cancel)

        self.btn_update = QtWidgets.QPushButton("Mettre à jour maintenant")
        self.btn_update.setProperty("neon", "success")
        self.btn_update.setFixedHeight(34)
        self.btn_update.clicked.connect(self._start_download)

        btn_row.addStretch()
        btn_row.addWidget(self.btn_later)
        btn_row.addWidget(self.btn_update)
        v.addLayout(btn_row)

    def _start_download(self):
        download_url = self.update_info.get("download_url")
        if not download_url:
            # Si pas de lien direct d'asset .exe, ouvrir la page GitHub release
            html_url = self.update_info.get("html_url")
            if html_url:
                QtGui.QDesktopServices.openUrl(QtCore.QUrl(html_url))
                self.accept()
                return
            QtWidgets.QMessageBox.warning(self, "Erreur", "Aucun lien de téléchargement direct trouvé pour cette mise à jour.")
            return

        self.prog_box.setVisible(True)
        self.btn_update.setEnabled(False)
        self.btn_update.setText("Téléchargement...")
        self.btn_later.setText("Annuler")
        self.lbl_status.setText("Connexion et démarrage du téléchargement...")

        filename = self.update_info.get("asset_name") or f"DofusOrganizer_Setup_v{self.update_info.get('latest_version')}.exe"
        self.downloader = UpdateDownloaderWorker(download_url, filename, self)
        self.downloader.progress.connect(self._on_progress)
        self.downloader.download_finished.connect(self._on_download_finished)
        self.downloader.download_failed.connect(self._on_download_failed)
        self.downloader.start()

    def _on_progress(self, downloaded: int, total: int):
        if total > 0:
            pct = int((downloaded / total) * 100)
            self.progress_bar.setValue(pct)
            dl_mb = downloaded / (1024 * 1024)
            tot_mb = total / (1024 * 1024)
            self.lbl_status.setText(f"Téléchargement : {dl_mb:.1f} Mo / {tot_mb:.1f} Mo ({pct}%)")
        else:
            dl_mb = downloaded / (1024 * 1024)
            self.progress_bar.setRange(0, 0)  # Indéterminé
            self.lbl_status.setText(f"Téléchargement : {dl_mb:.1f} Mo...")

    def _on_download_finished(self, installer_path: str):
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self.lbl_status.setText("Téléchargement terminé ! Lancement de l'installeur...")
        self.btn_update.setText("Installation en cours...")

        QtCore.QTimer.singleShot(800, lambda: launch_installer_and_exit(installer_path))

    def _on_download_failed(self, error_msg: str):
        self.btn_update.setEnabled(True)
        self.btn_update.setText("Réessayer")
        self.btn_later.setText("Fermer")
        self.lbl_status.setText(f"<span style='color:#FF5252;'>{error_msg}</span>")
        QtWidgets.QMessageBox.warning(self, "Erreur de mise à jour", error_msg)

    def _on_later_or_cancel(self):
        if self.downloader and self.downloader.isRunning():
            self.downloader.cancel()
            self.downloader.wait(1000)
        self.reject()

    def closeEvent(self, event: QtGui.QCloseEvent):
        if self.downloader and self.downloader.isRunning():
            self.downloader.cancel()
            self.downloader.wait(1000)
        super().closeEvent(event)
