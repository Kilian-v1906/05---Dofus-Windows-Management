# -*- mode: python ; coding: utf-8 -*-
"""
DofusOrganizer.spec
Configuration de compilation PyInstaller pour Dofus Organizer.
Génère une distribution autonome optimisée pour l'installeur Windows.
"""

import os
import sys

block_cipher = None

workspace_dir = os.path.abspath(SPECPATH)

added_datas = [
    (os.path.join(workspace_dir, "assets"), "assets"),
    (os.path.join(workspace_dir, "themes"), "themes"),
    (os.path.join(workspace_dir, "profiles"), "profiles"),
]

hidden_imports = [
    "keyboard",
    "win32gui",
    "win32con",
    "win32process",
    "win32api",
    "psutil",
    "pygetwindow",
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "shiboken6",
]

excluded_modules = [
    "tkinter",
    "unittest",
    "scipy",
    "numpy",
    "matplotlib",
    "PIL",
]

a = Analysis(
    ["main.py"],
    pathex=[workspace_dir],
    binaries=[],
    datas=added_datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excluded_modules,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher,
)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="DofusOrganizer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(workspace_dir, "assets", "icon", "dwm.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="DofusOrganizer",
)
