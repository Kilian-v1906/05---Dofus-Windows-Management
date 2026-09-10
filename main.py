"""
main.py
Point d'entrée principal de l'application Dofus Organizer.
"""

import sys
from PySide6.QtWidgets import QApplication
from utils.paths import apply_theme_from_settings, load_icon
from utils.winfocus import release_stuck_modifiers
from app.ui_main import DofusOrganizer


def main():
    # Débloquer d'éventuelles touches modificatrices (Alt/Ctrl/Shift) résiduelles
    release_stuck_modifiers()

    app = QApplication(sys.argv)
    app.setApplicationName("DofusOrganizer")
    app.setOrganizationName("Kilian")

    ico = load_icon("dwm.ico")
    if not ico.isNull():
        app.setWindowIcon(ico)

    # Appliquer le thème sauvegardé
    apply_theme_from_settings(app)

    win = DofusOrganizer()
    win.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()