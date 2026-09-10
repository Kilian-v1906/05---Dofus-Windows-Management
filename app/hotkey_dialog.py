"""
app/hotkey_dialog.py
Boîte de dialogue modale moderne de capture de raccourci clavier Qt.
"""

from PySide6 import QtWidgets, QtGui, QtCore
from PySide6.QtCore import Qt, Signal
from utils.hotkeys import (
    qt_key_event_to_hotkey_string,
    format_hotkey_display,
    normalize_hotkey_string,
)
from utils.paths import load_icon


class HotkeyCaptureDialog(QtWidgets.QDialog):
    hotkey_selected = Signal(str)

    def __init__(self, title: str = "Définir un raccourci", parent=None, current_hotkey: str = ""):
        super().__init__(parent)
        self.setWindowTitle(title)
        ico = load_icon("dwm.ico")
        if not ico.isNull():
            self.setWindowIcon(ico)
        self.setModal(True)
        self.setFixedSize(380, 160)

        self._captured_hotkey: str = ""

        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(20, 20, 20, 20)
        v.setSpacing(14)

        self.label = QtWidgets.QLabel(
            "Appuyez sur la touche ou combinaison souhaitée...\n(Ex: Tab, Ctrl+Tab, F1, &, Pavé num...)"
        )
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet("font-size:13px; font-weight:600;")
        v.addWidget(self.label)

        if current_hotkey:
            curr_str = format_hotkey_display(current_hotkey)
            self.lbl_curr = QtWidgets.QLabel(f"Raccourci actuel : {curr_str}")
            self.lbl_curr.setAlignment(Qt.AlignCenter)
            self.lbl_curr.setProperty("muted", True)
            v.addWidget(self.lbl_curr)

        row = QtWidgets.QHBoxLayout()
        row.setSpacing(10)

        self.btn_clear = QtWidgets.QPushButton("Effacer le raccourci")
        self.btn_clear.clicked.connect(self._on_clear)

        self.btn_cancel = QtWidgets.QPushButton("Annuler")
        self.btn_cancel.clicked.connect(self.reject)

        row.addStretch()
        row.addWidget(self.btn_clear)
        row.addWidget(self.btn_cancel)
        row.addStretch()
        v.addLayout(row)

    def keyPressEvent(self, event: QtGui.QKeyEvent):
        key = event.key()
        if key == Qt.Key_Escape:
            self.reject()
            return

        hk = qt_key_event_to_hotkey_string(event)
        if hk:
            normalized = normalize_hotkey_string(hk)
            if normalized:
                self._captured_hotkey = normalized
                self.hotkey_selected.emit(normalized)
                self.accept()
                return

        super().keyPressEvent(event)

    def _on_clear(self):
        self._captured_hotkey = ""
        self.hotkey_selected.emit("")
        self.accept()
