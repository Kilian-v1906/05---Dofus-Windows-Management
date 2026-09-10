import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QComboBox, QCheckBox, QListWidget, QListWidgetItem, QFrame
)
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QIcon
import win32gui

class DofusWindowManager(QMainWindow):
    def __init__(self):
        super().__init__()

        # Fenêtre principale
        self.setWindowTitle("Dofus Window Manager by Kilian")
        self.setGeometry(100, 100, 800, 600)

        # Widget central
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Layout principal
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)

        # Bannière de titre
        banner_layout = QHBoxLayout()

        # Icône Account
        account_icon = QPushButton()
        account_icon.setIcon(QIcon("images/account.svg"))
        account_icon.setIconSize(QSize(32, 32))
        account_icon.setFlat(True)
        account_icon.clicked.connect(self.save_profile)
        banner_layout.addWidget(account_icon)

        # Liste déroulante pour les profils
        self.profile_dropdown = QComboBox()
        self.profile_dropdown.addItems(["Profil 1", "Profil 2", "Profil 3"])
        self.profile_dropdown.setMaximumWidth(200)
        banner_layout.addWidget(self.profile_dropdown, alignment=Qt.AlignCenter)

        # Icône Settings
        settings_icon = QPushButton()
        settings_icon.setIcon(QIcon("images/settings.svg"))
        settings_icon.setIconSize(QSize(32, 32))
        settings_icon.setFlat(True)
        settings_icon.clicked.connect(self.open_settings)
        banner_layout.addWidget(settings_icon)

        main_layout.addLayout(banner_layout)

        # Titres des colonnes
        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel("Nom du personnage"))
        header_layout.addWidget(QLabel("Classe"))
        header_layout.addWidget(QLabel("Ordre"))
        main_layout.addLayout(header_layout)

        # Liste des fenêtres
        self.window_list = QListWidget()
        main_layout.addWidget(self.window_list)

        # Boutons
        button_layout = QHBoxLayout()

        refresh_button = QPushButton("Actualiser")
        refresh_button.clicked.connect(self.refresh_windows)
        button_layout.addWidget(refresh_button)

        play_button = QPushButton("Jouer")
        play_button.clicked.connect(self.minimal_view)
        button_layout.addWidget(play_button)

        main_layout.addLayout(button_layout)

        # Ajouter des fenêtres pré-enregistrées pour les tests
        self.load_test_windows()

    def load_test_windows(self):
        # Ajout de fenêtres fictives pour tests
        test_windows = ["Dofus - Personnage 1", "Dofus - Personnage 2", "Dofus - Personnage 3"]
        for window in test_windows:
            self.add_window_item(window)

    def refresh_windows(self):
        # Recherche des fenêtres Dofus
        self.window_list.clear()
        def callback(hwnd, extra):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if "Dofus" in title:
                    self.add_window_item(title)
        win32gui.EnumWindows(callback, None)

    def add_window_item(self, window_title):
        item = QListWidgetItem()

        # Conteneur pour les widgets personnalisés
        container = QWidget()
        container_layout = QHBoxLayout()
        container.setLayout(container_layout)

        # Checkbox
        checkbox = QCheckBox()
        container_layout.addWidget(checkbox)

        # Bouton pour drag-and-drop
        drag_button = QPushButton()
        drag_button.setText("≡")
        drag_button.setFlat(True)
        container_layout.addWidget(drag_button)

        # Textboxes
        name_edit = QLineEdit(window_title)
        class_edit = QLineEdit("Classe")
        order_edit = QLineEdit("Ordre")
        container_layout.addWidget(name_edit)
        container_layout.addWidget(class_edit)
        container_layout.addWidget(order_edit)

        item.setSizeHint(container.sizeHint())
        self.window_list.addItem(item)
        self.window_list.setItemWidget(item, container)

    def save_profile(self):
        print("Profil sauvegardé :", self.profile_dropdown.currentText())

    def open_settings(self):
        print("Ouverture des paramètres")

    def minimal_view(self):
        print("Passage à la vue minimaliste")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = DofusWindowManager()
    window.show()
    sys.exit(app.exec_())
