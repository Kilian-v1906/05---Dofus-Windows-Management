"""
utils/winfocus.py
Activation et mise au premier plan fiable des fenêtres sous Windows 10 / 11.
Contourne les restrictions de l'API Windows (AttachThreadInput, AllowSetForegroundWindow, SwitchToThisWindow).
"""

import ctypes
import time
from typing import Optional
import win32con
import win32gui
import win32process
import pywintypes

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

SPI_SETFOREGROUNDLOCKTIMEOUT = 0x2001
SPIF_SENDCHANGE = 0x02
ASFW_ANY = -1


def release_stuck_modifiers() -> None:
    """
    Vérifie et libère les touches modificatrices (Alt, Ctrl, Shift)
    si elles sont restées bloquées par d'anciennes opérations Windows.
    """
    VK_MENU = 0x12
    VK_CONTROL = 0x11
    VK_SHIFT = 0x10
    KEYEVENTF_KEYUP = 0x0002
    try:
        for vk in (VK_MENU, VK_CONTROL, VK_SHIFT):
            # Si le bit de poids fort est à 1, la touche est actuellement enfoncée
            if user32.GetAsyncKeyState(vk) & 0x8000:
                user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
    except Exception:
        pass


def force_foreground(hwnd: int, delay_ms: int = 0) -> bool:
    """
    Force la fenêtre ciblée au premier plan avec le focus actif
    sans injecter de touches artificielles (Alt) et sans bloquer
    les files de messages du clavier ou de la souris.
    """
    if not hwnd or not win32gui.IsWindow(hwnd):
        return False

    # Si la fenêtre est déjà celle au premier plan, rien à faire
    fg_hwnd = win32gui.GetForegroundWindow()
    if fg_hwnd == hwnd and not win32gui.IsIconic(hwnd):
        return True

    cur_tid = kernel32.GetCurrentThreadId()
    fg_tid = 0
    attached = False

    try:
        # 1. Autoriser le changement de fenêtre au premier plan
        user32.AllowSetForegroundWindow(ASFW_ANY)
        user32.SystemParametersInfoW(SPI_SETFOREGROUNDLOCKTIMEOUT, 0, 0, SPIF_SENDCHANGE)

        # 2. Identifier le thread actuellement au premier plan
        if fg_hwnd and win32gui.IsWindow(fg_hwnd):
            fg_tid, _ = win32process.GetWindowThreadProcessId(fg_hwnd)

        # 3. Attacher temporairement les threads d'entrée si nécessaire
        # UNIQUEMENT le thread courant au thread actif, SANS simuler d'appui sur Alt
        if fg_tid and cur_tid and fg_tid != cur_tid:
            attached = bool(user32.AttachThreadInput(cur_tid, fg_tid, True))

        # 4. Restaurer la fenêtre si elle est minimisée
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        else:
            win32gui.ShowWindow(hwnd, win32con.SW_SHOW)

        if delay_ms > 0:
            time.sleep(delay_ms / 1000.0)

        # 5. Bascule Shell et activation
        try:
            user32.SwitchToThisWindow(hwnd, True)
        except Exception:
            pass

        win32gui.BringWindowToTop(hwnd)
        win32gui.SetForegroundWindow(hwnd)
        win32gui.SetActiveWindow(hwnd)

        # 6. S'assurer de la position Z-Order (TopMost puis NotTopMost si nécessaire)
        win32gui.SetWindowPos(
            hwnd,
            win32con.HWND_TOP,
            0, 0, 0, 0,
            win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_SHOWWINDOW,
        )

        return True

    except pywintypes.error as e:
        if getattr(e, "winerror", 0) != 5:
            print(f"[winfocus] Erreur Win32 sur hwnd {hwnd}: {e}")
        return False
    except Exception as e:
        print(f"[winfocus] Erreur inattendue sur hwnd {hwnd}: {e}")
        return False
    finally:
        # 7. Détachement immédiat et obligatoire du thread
        if attached and cur_tid and fg_tid:
            try:
                user32.AttachThreadInput(cur_tid, fg_tid, False)
            except Exception:
                pass
        # Débloquer d'éventuels états fantômes
        release_stuck_modifiers()


