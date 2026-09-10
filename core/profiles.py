"""
core/profiles.py
Module de gestion et persistance des profils d'équipes Dofus (fichiers JSON).
"""

import json
import os
import shutil
from typing import List, Dict, Any, Optional, Tuple
from utils.paths import get_user_data_dir, resource_path, app_executable_dir


def get_profiles_dir() -> str:
    """
    Retourne le dossier des profils utilisateur avec initialisation automatique.
    - Mode portable si portable.txt est présent dans le dossier de l'exécutable.
    - Sinon standard Windows : %APPDATA%/DofusOrganizer/profiles.
    - Initialise automatiquement les profils par défaut depuis les ressources si vide.
    """
    exe_dir = app_executable_dir()
    if os.path.isfile(os.path.join(exe_dir, "portable.txt")):
        target_dir = os.path.join(exe_dir, "profiles")
    else:
        target_dir = os.path.join(get_user_data_dir(), "profiles")

    os.makedirs(target_dir, exist_ok=True)

    # Si le dossier utilisateur est vide, copier les profils par défaut fournis avec l'application
    existing_jsons = [f for f in os.listdir(target_dir) if f.lower().endswith(".json")]
    if not existing_jsons:
        # Vérifier d'abord dans les ressources bundle / dossier projet
        bundled_dirs = [
            resource_path("profiles"),
            os.path.join(exe_dir, "profiles"),
        ]
        for b_dir in bundled_dirs:
            if os.path.isdir(b_dir) and os.path.abspath(b_dir) != os.path.abspath(target_dir):
                for fn in os.listdir(b_dir):
                    if fn.lower().endswith(".json"):
                        src = os.path.join(b_dir, fn)
                        dst = os.path.join(target_dir, fn)
                        try:
                            shutil.copy2(src, dst)
                        except Exception:
                            pass
                # Si on a copié des fichiers, on s'arrête
                if any(f.lower().endswith(".json") for f in os.listdir(target_dir)):
                    break

    return target_dir


PROFILES_DIR = get_profiles_dir()


def open_profiles_directory() -> bool:
    """Ouvre le dossier des profils dans l'Explorateur de fichiers Windows."""
    try:
        p = get_profiles_dir()
        if os.name == "nt":
            os.startfile(p)
            return True
    except Exception as e:
        print(f"[profiles] Erreur ouverture dossier profils: {e}")
    return False


def _profile_path(name: str) -> str:
    """Retourne le chemin absolu du fichier JSON pour un profil donné."""
    sanitized_name = name.strip()
    return os.path.join(get_profiles_dir(), f"{sanitized_name}.json")


def get_profiles_list() -> List[str]:
    """Retourne la liste triée des noms de profils disponibles."""
    p_dir = get_profiles_dir()
    if not os.path.exists(p_dir):
        return []
    res = []
    for fn in os.listdir(p_dir):
        if fn.lower().endswith(".json"):
            res.append(os.path.splitext(fn)[0])
    res.sort(key=lambda s: s.lower())
    return res



def load_profile(name: str) -> Optional[Dict[str, Any]]:
    """Charge les données d'un profil depuis son fichier JSON."""
    if not name:
        return None
    path = _profile_path(name)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
    except Exception as e:
        print(f"[profiles] Erreur lors du chargement de '{name}': {e}")
    return None


def save_profile(
    name: str,
    windows: List[Dict[str, Any]],
    extra: Optional[Dict[str, Any]] = None,
    primary: Optional[bool] = None,
) -> bool:
    """
    Sauvegarde un profil dans profiles/<name>.json.
    windows: [{pseudo, classe, enabled?, hotkey?, handle?}, ...]
    extra:   dict optionnel (ex: global_hotkeys, settings...)
    """
    if not name or not name.strip():
        return False

    os.makedirs(PROFILES_DIR, exist_ok=True)
    path = _profile_path(name.strip())

    # Nettoyage des handles Windows avant persistance (les handles changent à chaque lancement)
    clean_windows = []
    for w in windows:
        clean_w = {
            "pseudo": str(w.get("pseudo", "")).strip(),
            "classe": str(w.get("classe", "")).strip(),
            "enabled": bool(w.get("enabled", True)),
        }
        if w.get("hotkey"):
            clean_w["hotkey"] = str(w.get("hotkey")).strip()
        clean_windows.append(clean_w)

    payload: Dict[str, Any] = {
        "profile_name": name.strip(),
        "windows": clean_windows,
    }

    if primary is not None:
        payload["primary"] = bool(primary)
    else:
        existing = load_profile(name)
        if existing and "primary" in existing:
            payload["primary"] = existing["primary"]

    if extra:
        payload.update(extra)

    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"[profiles] Erreur lors de la sauvegarde de '{name}': {e}")
        return False


def delete_profile(name: str) -> bool:
    """Supprime le fichier JSON du profil."""
    path = _profile_path(name)
    if os.path.isfile(path):
        try:
            os.remove(path)
            return True
        except Exception as e:
            print(f"[profiles] Erreur suppression '{name}': {e}")
            return False
    return False


def rename_profile(old_name: str, new_name: str) -> bool:
    """Renomme un profil existant."""
    old_path = _profile_path(old_name)
    new_path = _profile_path(new_name)
    if not os.path.isfile(old_path) or os.path.exists(new_path):
        return False
    try:
        data = load_profile(old_name) or {}
        data["profile_name"] = new_name.strip()
        with open(new_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        os.remove(old_path)
        return True
    except Exception as e:
        print(f"[profiles] Erreur renommage '{old_name}' -> '{new_name}': {e}")
        return False


def is_profile_primary(name: str) -> bool:
    """Vérifie si le profil est marqué comme principal."""
    d = load_profile(name) or {}
    return bool(d.get("primary", False))


def set_profile_primary(name: str, is_primary: bool) -> bool:
    """Définit ou retire le statut de profil principal."""
    d = load_profile(name)
    if not d:
        return False
    # Si on active un profil comme principal, on désactive les autres
    if is_primary:
        for other in get_profiles_list():
            if other.lower() != name.lower():
                od = load_profile(other)
                if od and od.get("primary"):
                    od["primary"] = False
                    try:
                        with open(_profile_path(other), "w", encoding="utf-8") as f:
                            json.dump(od, f, ensure_ascii=False, indent=4)
                    except Exception:
                        pass

    d["primary"] = bool(is_primary)
    try:
        with open(_profile_path(name), "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=4)
        return True
    except Exception as e:
        print(f"[profiles] Erreur mise à jour statut principal '{name}': {e}")
        return False


def get_primary_profile() -> Optional[str]:
    """Retourne le nom du profil principal s'il existe."""
    for name in get_profiles_list():
        if is_profile_primary(name):
            return name
    return None


def get_all_profiles_data() -> List[Dict[str, Any]]:
    """Retourne les données de tous les profils existants."""
    res = []
    for name in get_profiles_list():
        d = load_profile(name)
        if d:
            res.append(d)
    return res


def _signature_from_windows(wins: List[Dict[str, Any]]) -> Tuple[Tuple[str, str], ...]:
    """Signature unique basée sur la séquence ordonnée (pseudo, classe)."""
    return tuple((str(w.get("pseudo", "")).strip().lower(), str(w.get("classe", "")).strip().lower()) for w in wins)


def find_best_matching_profile(open_pseudos: List[str] | set[str]) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    """
    Trouve le profil qui correspond le mieux aux pseudos des fenêtres Dofus actuellement ouvertes.
    Retourne (nom_profil, data_profil) ou (None, None) si aucun profil ne correspond.
    """
    open_set = {str(p).strip().lower() for p in open_pseudos if str(p).strip()}
    if not open_set:
        return None, None

    best_name = None
    best_data = None
    best_score = -1

    for name in get_profiles_list():
        data = load_profile(name)
        if not data:
            continue

        wins = data.get("windows", [])
        prof_pseudos = [str(w.get("pseudo", "")).strip().lower() for w in wins if w.get("pseudo")]
        prof_set = set(prof_pseudos)

        if not prof_set:
            continue

        is_prim = bool(data.get("primary", False))
        intersection = prof_set.intersection(open_set)
        num_matches = len(intersection)

        if num_matches == 0:
            continue

        if prof_set == open_set:
            # Correspondance exacte parfaite
            score = 10000 + (100 if is_prim else 0)
        elif prof_set.issubset(open_set):
            # Tous les personnages du profil sont ouverts (avec potentiellement d'autres)
            score = 5000 + len(prof_set) * 100 + (50 if is_prim else 0) - (len(open_set) - len(prof_set)) * 10
        elif open_set.issubset(prof_set):
            # Les fenêtres ouvertes forment un sous-ensemble du profil
            score = 2000 + len(open_set) * 100 + (50 if is_prim else 0) - (len(prof_set) - len(open_set)) * 10
        else:
            # Recouvrement partiel
            score = num_matches * 50 + (10 if is_prim else 0) - abs(len(prof_set) - len(open_set)) * 5

        if score > best_score:
            best_score = score
            best_name = name
            best_data = data

    if best_score >= 1000:
        return best_name, best_data

    return None, None

