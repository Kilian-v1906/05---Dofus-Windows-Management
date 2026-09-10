"""
core/updater.py
Gestionnaire de versions et de mises à jour automatiques pour Dofus Organizer.
Prend en charge GitHub Releases et URLs JSON directes avec téléchargement asynchrone.
"""

import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.request
from typing import Optional, Tuple, Dict, Any
from PySide6.QtCore import QThread, Signal
from utils.paths import get_app_settings

APP_VERSION = "1.0.0"

# Dépôt GitHub par défaut pour les releases (peut être surchargé dans QSettings)
DEFAULT_GITHUB_REPO = "kilian/dofus-organizer"


def parse_version(v_str: str) -> Tuple[int, ...]:
    """Convertit une chaîne de version (ex: 'v1.2.3' ou '1.0.0-beta') en tuple d'entiers pour comparaison."""
    if not v_str:
        return (0,)
    clean = v_str.strip().lstrip("vV")
    parts = re.split(r"[^\d]+", clean)
    nums = []
    for p in parts:
        if p.isdigit():
            nums.append(int(p))
    return tuple(nums) if nums else (0,)


def is_newer_version(latest: str, current: str = APP_VERSION) -> bool:
    """Retourne True si 'latest' est strictement plus récent que 'current'."""
    return parse_version(latest) > parse_version(current)


class UpdateCheckerWorker(QThread):
    """Vérificateur asynchrone de mise à jour pour ne pas bloquer l'UI Qt."""

    check_finished = Signal(dict)
    check_failed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = get_app_settings()

    def run(self):
        try:
            custom_url = str(self.settings.value("updates/custom_json_url", "")).strip()
            repo = str(self.settings.value("updates/github_repo", DEFAULT_GITHUB_REPO)).strip()

            if custom_url:
                url = custom_url
            else:
                url = f"https://api.github.com/repos/{repo}/releases/latest"

            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": f"DofusOrganizer/{APP_VERSION} (Windows)",
                    "Accept": "application/vnd.github.v3+json",
                },
            )

            with urllib.request.urlopen(req, timeout=8) as response:
                if response.status != 200:
                    self.check_failed.emit(f"Erreur HTTP {response.status}")
                    return
                data = json.loads(response.read().decode("utf-8"))

            latest_version = str(data.get("tag_name", data.get("version", ""))).lstrip("vV")
            release_notes = data.get("body", data.get("description", "Aucune note de mise à jour disponible."))

            # Trouver le fichier téléchargeable (.exe)
            download_url = ""
            asset_name = ""
            assets = data.get("assets", [])
            for a in assets:
                name = a.get("name", "")
                if name.lower().endswith(".exe"):
                    # Priorité à l'installeur Setup.exe
                    if "setup" in name.lower() or not download_url:
                        download_url = a.get("browser_download_url", "")
                        asset_name = name

            if not download_url:
                download_url = data.get("download_url", "")

            update_available = is_newer_version(latest_version, APP_VERSION)

            result = {
                "update_available": update_available,
                "current_version": APP_VERSION,
                "latest_version": latest_version,
                "release_notes": release_notes,
                "download_url": download_url,
                "asset_name": asset_name or f"DofusOrganizer_Setup_v{latest_version}.exe",
                "html_url": data.get("html_url", ""),
            }
            self.check_finished.emit(result)

        except urllib.error.HTTPError as e:
            if e.code == 404:
                self.check_failed.emit("Dépôt ou release introuvable (HTTP 404).")
            else:
                self.check_failed.emit(f"Erreur serveur HTTP {e.code}")
        except urllib.error.URLError as e:
            self.check_failed.emit("Impossible de contacter le serveur de mise à jour (vérifiez votre connexion internet).")
        except Exception as e:
            self.check_failed.emit(f"Erreur vérification mise à jour: {e}")


class UpdateDownloaderWorker(QThread):
    """Téléchargeur asynchrone du nouvel installeur avec suivi de progression."""

    progress = Signal(int, int)  # (bytes_downloaded, total_bytes)
    download_finished = Signal(str)  # local file path
    download_failed = Signal(str)

    def __init__(self, download_url: str, filename: str, parent=None):
        super().__init__(parent)
        self.download_url = download_url
        self.filename = filename
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        if not self.download_url:
            self.download_failed.emit("URL de téléchargement invalide.")
            return

        try:
            temp_dir = os.path.join(tempfile.gettempdir(), "DofusOrganizer_Update")
            os.makedirs(temp_dir, exist_ok=True)
            local_path = os.path.join(temp_dir, self.filename)

            req = urllib.request.Request(
                self.download_url,
                headers={"User-Agent": f"DofusOrganizer/{APP_VERSION} (Windows)"},
            )

            with urllib.request.urlopen(req, timeout=15) as response:
                total_length = response.headers.get("content-length")
                total_bytes = int(total_length) if total_length and total_length.isdigit() else 0

                downloaded = 0
                block_size = 64 * 1024  # 64 KB chunks

                with open(local_path, "wb") as out_file:
                    while True:
                        if self._is_cancelled:
                            self.download_failed.emit("Téléchargement annulé.")
                            return
                        chunk = response.read(block_size)
                        if not chunk:
                            break
                        out_file.write(chunk)
                        downloaded += len(chunk)
                        self.progress.emit(downloaded, total_bytes)

            self.download_finished.emit(local_path)

        except Exception as e:
            self.download_failed.emit(f"Erreur lors du téléchargement : {e}")


def launch_installer_and_exit(installer_path: str):
    """Lance l'installeur téléchargé et quitte proprement l'application courante."""
    if not os.path.isfile(installer_path):
        return False
    try:
        # Lancement détaché de l'installeur
        subprocess.Popen(
            [installer_path],
            shell=False,
            close_fds=True,
            creationflags=subprocess.DETACHED_PROCESS if os.name == "nt" else 0,
        )
        # Quitter l'application
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app:
            app.quit()
        else:
            sys.exit(0)
        return True
    except Exception as e:
        print(f"[updater] Erreur lancement installeur: {e}")
        return False
