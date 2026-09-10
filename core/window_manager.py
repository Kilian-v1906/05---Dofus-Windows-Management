"""
core/window_manager.py
Détection, filtrage de processus et parsing des fenêtres de jeu Dofus.
Compatible Dofus 2, Dofus 3 (Unity) et Dofus Retro.
"""

import re
from typing import List, Dict, Any, Optional
import win32con
import win32gui
import win32process
import psutil

# Regex pour détecter les formats de version type "3.3.18.17", "1.42.3", "3.0.1", etc.
VERSION_PATTERN = re.compile(r"\d+(?:\.\d+){1,4}$")


def _is_dofus_process(hwnd: int) -> bool:
    """
    Vérifie si la fenêtre appartient à un processus client Dofus
    (exclut explicitement les processus Ankama Launcher, Update, etc.).
    """
    try:
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        if pid <= 0:
            return False
        p = psutil.Process(pid)
        name = (p.name() or "").lower()
        exe = ""
        try:
            exe = (p.exe() or "").lower()
        except Exception:
            pass

        full_check = f"{name} {exe}"

        # Mots-clés de processus autorisés
        is_dofus = any(k in full_check for k in ("dofus", "dofus unity", "dofusretro", "zaap"))
        # Mots-clés exclus (launcher, updater, crash reporter)
        is_excluded = any(k in full_check for k in ("launcher", "updater", "crash", "bugreport", "installer", "cef"))

        return is_dofus and not is_excluded
    except (psutil.NoSuchProcess, psutil.AccessDenied, Exception):
        return False


def _parse_dofus_title(title: str) -> Optional[Dict[str, str]]:
    """
    Parse robuste du titre de la fenêtre Dofus.
    Exemples classiques :
      - 'Compte-Pseudo - Classe - 3.3.18.17 - Release'
      - 'Mara-Cuja - Sram - 3.3.18.17 - Release'
      - 'MonPersonnage - Iop - 3.0.0'
      - 'MonPerso - Cra - Ocre - Release'
    Retourne dict {pseudo, classe, version} ou None si non conforme.
    """
    if not title:
        return None

    clean_title = title.strip()
    parts = clean_title.split(" - ")
    if len(parts) < 2:
        return None

    # Si 2 parties (ex: "Pseudo - Dofus Retro")
    if len(parts) == 2:
        pseudo = parts[0].strip()
        classe = parts[1].strip()
        return {"pseudo": pseudo, "classe": classe, "version": ""}

    # 3 parties ou plus : on cherche un segment version de droite à gauche
    end = len(parts) - 1
    # Ignorer un suffixe de build type 'Release' ou 'Debug'
    if parts[end].strip().lower() in ("release", "debug", "beta", "alpha") and end > 1:
        end -= 1

    ver_idx = None
    for i in range(end, -1, -1):
        seg = parts[i].strip()
        if VERSION_PATTERN.fullmatch(seg):
            ver_idx = i
            break

    if ver_idx is not None and ver_idx >= 2:
        # Segment avant la version = classe
        version = parts[ver_idx].strip()
        classe = parts[ver_idx - 1].strip()
        pseudo = " - ".join(parts[: ver_idx - 1]).strip()
    elif ver_idx is not None and ver_idx == 1:
        version = parts[ver_idx].strip()
        classe = "Dofus"
        pseudo = parts[0].strip()
    else:
        # Pas de segment version évident : on prend [Pseudo, Classe, ...]
        pseudo = parts[0].strip()
        classe = parts[1].strip()
        version = parts[2].strip() if len(parts) > 2 else ""

    if not pseudo:
        return None

    return {
        "pseudo": pseudo,
        "classe": classe if classe else "Dofus",
        "version": version,
    }


def get_dofus_windows() -> List[Dict[str, Any]]:
    """
    Détecte et retourne toutes les fenêtres Dofus actives.
    Résultat: list[dict] = [{ 'title', 'handle', 'pseudo', 'classe', 'version', 'pid' }, ...]
    Trié par pseudo pour une stabilité d'affichage par défaut.
    """
    results: List[Dict[str, Any]] = []
    seen_handles = set()

    def _enum_cb(hwnd: int, _):
        try:
            if not win32gui.IsWindow(hwnd):
                return True
            if not win32gui.IsWindowVisible(hwnd):
                return True

            # Exclure les fenêtres de type toolwindow sans barre des tâches
            exstyle = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            if exstyle & win32con.WS_EX_TOOLWINDOW:
                return True

            # Exclure les fenêtres possédées (owned windows / popups)
            owner = win32gui.GetWindow(hwnd, win32con.GW_OWNER)
            if owner != 0:
                return True

            # Exclure les fenêtres de taille minuscule (splash / helpers)
            rect = win32gui.GetWindowRect(hwnd)
            w = rect[2] - rect[0]
            h = rect[3] - rect[1]
            if w < 100 or h < 100:
                return True

            title = win32gui.GetWindowText(hwnd) or ""
            title = title.strip()
            if not title:
                return True

            # Parsing du titre
            parsed = _parse_dofus_title(title)
            if not parsed:
                return True

            # Vérification du processus
            if not _is_dofus_process(hwnd):
                return True

            if hwnd in seen_handles:
                return True
            seen_handles.add(hwnd)

            _, pid = win32process.GetWindowThreadProcessId(hwnd)

            results.append({
                "title": title,
                "handle": hwnd,
                "pseudo": parsed["pseudo"],
                "classe": parsed["classe"],
                "version": parsed.get("version", ""),
                "pid": pid,
            })
        except Exception:
            pass
        return True

    try:
        win32gui.EnumWindows(_enum_cb, None)
    except Exception as e:
        # Code 122 survient en environnement non-interactif sans bureau graphique actif
        if getattr(e, "winerror", None) != 122:
            print(f"[window_manager] EnumWindows exception: {e}")

    # Tri par ordre alphabétique du pseudo
    results.sort(key=lambda w: (w["pseudo"].lower(), w["classe"].lower()))
    return results
