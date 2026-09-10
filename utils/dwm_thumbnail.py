"""
utils/dwm_thumbnail.py
Intégration de l'API native Windows Desktop Window Manager (DWM)
pour l'affichage d'aperçus miniatures vidéo en direct (Picture-in-Picture).
Rendu 100% matériel GPU via dwmapi.dll (0% CPU, 60 FPS, sans injection client).
"""

import ctypes
from ctypes import wintypes
from typing import Optional

from PySide6 import QtWidgets, QtCore, QtGui
from PySide6.QtCore import Qt, QPoint, Signal, QTimer
import win32gui

# Constantes DWM
DWM_TNP_RECTDESTINATION = 0x00000001
DWM_TNP_RECTSOURCE = 0x00000002
DWM_TNP_OPACITY = 0x00000004
DWM_TNP_VISIBLE = 0x00000008
DWM_TNP_SOURCECLIENTAREAONLY = 0x00000010


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", wintypes.LONG),
        ("top", wintypes.LONG),
        ("right", wintypes.LONG),
        ("bottom", wintypes.LONG),
    ]


class DWM_THUMBNAIL_PROPERTIES(ctypes.Structure):
    _fields_ = [
        ("dwFlags", wintypes.DWORD),
        ("rcDestination", RECT),
        ("rcSource", RECT),
        ("opacity", ctypes.c_ubyte),
        ("fVisible", wintypes.BOOL),
        ("fSourceClientAreaOnly", wintypes.BOOL),
    ]


try:
    _dwmapi = ctypes.windll.dwmapi
except Exception:
    _dwmapi = None


def is_dwm_available() -> bool:
    """Vérifie si l'API DWM est disponible sur le système."""
    return _dwmapi is not None and hasattr(_dwmapi, "DwmRegisterThumbnail")


def register_dwm_thumbnail(dest_hwnd: int, src_hwnd: int) -> Optional[int]:
    """
    Enregistre un flux miniature DWM de la fenêtre source vers la fenêtre destination.
    Retourne l'identifiant de miniature ou None en cas d'échec.
    """
    if not is_dwm_available() or not dest_hwnd or not src_hwnd:
        return None
    if not win32gui.IsWindow(dest_hwnd) or not win32gui.IsWindow(src_hwnd):
        return None

    thumb_id = ctypes.c_void_p()
    hr = _dwmapi.DwmRegisterThumbnail(
        dest_hwnd,
        src_hwnd,
        ctypes.byref(thumb_id)
    )
    if hr == 0 and thumb_id.value is not None:
        return thumb_id.value
    return None


def update_dwm_thumbnail(
    thumb_id: int,
    dest_rect: tuple[int, int, int, int],
    visible: bool = True,
    opacity: int = 255,
    client_area_only: bool = True,
) -> bool:
    """
    Met à jour la zone de destination, la visibilité et l'opacité d'une miniature DWM.
    dest_rect : (left, top, right, bottom) relatif au client area du HWND de destination.
    """
    if not is_dwm_available() or not thumb_id:
        return False

    props = DWM_THUMBNAIL_PROPERTIES()
    props.dwFlags = (
        DWM_TNP_RECTDESTINATION
        | DWM_TNP_VISIBLE
        | DWM_TNP_OPACITY
        | DWM_TNP_SOURCECLIENTAREAONLY
    )
    props.rcDestination = RECT(
        int(dest_rect[0]),
        int(dest_rect[1]),
        int(dest_rect[2]),
        int(dest_rect[3]),
    )
    props.opacity = max(0, min(255, int(opacity)))
    props.fVisible = bool(visible)
    props.fSourceClientAreaOnly = bool(client_area_only)

    hr = _dwmapi.DwmUpdateThumbnailProperties(
        ctypes.c_void_p(thumb_id),
        ctypes.byref(props)
    )
    return hr == 0


def unregister_dwm_thumbnail(thumb_id: Optional[int]) -> None:
    """Libère une ressource de miniature DWM."""
    if is_dwm_available() and thumb_id:
        try:
            _dwmapi.DwmUnregisterThumbnail(ctypes.c_void_p(thumb_id))
        except Exception:
            pass


class DwmThumbnailWidget(QtWidgets.QWidget):
    """
    Widget PySide6 hébergeant une miniature DWM en direct.
    Gère automatiquement la synchronisation des coordonnées par rapport à la fenêtre parente.
    """

    clicked = Signal()

    def __init__(self, source_hwnd: int, parent=None):
        super().__init__(parent)
        self.source_hwnd = source_hwnd
        self._thumb_id: Optional[int] = None
        self._is_registered = False

        self.setAttribute(Qt.WA_NativeWindow, True)
        self.setAttribute(Qt.WA_OpaquePaintEvent, False)
        self.setCursor(Qt.PointingHandCursor)

        # Timer de recalage de position après redimensionnements ou déplacements
        self._update_timer = QTimer(self)
        self._update_timer.setSingleShot(True)
        self._update_timer.setInterval(30)
        self._update_timer.timeout.connect(self._sync_thumbnail_geometry)

    def set_source_hwnd(self, hwnd: int):
        if self.source_hwnd != hwnd:
            self.unregister()
            self.source_hwnd = hwnd
            if self.isVisible():
                self.register()

    def register(self):
        if self._is_registered or not self.source_hwnd:
            return

        top_win = self.window()
        if not top_win or not top_win.isVisible():
            return

        dest_hwnd = int(top_win.winId())
        self._thumb_id = register_dwm_thumbnail(dest_hwnd, self.source_hwnd)
        if self._thumb_id:
            self._is_registered = True
            self._sync_thumbnail_geometry()

    def unregister(self):
        if self._thumb_id:
            unregister_dwm_thumbnail(self._thumb_id)
            self._thumb_id = None
        self._is_registered = False

    def _sync_thumbnail_geometry(self):
        if not self._is_registered or not self._thumb_id:
            return

        top_win = self.window()
        if not top_win or not self.isVisible():
            return

        # Calculer le rectangle dans l'espace client de la fenêtre parente racine
        top_left = self.mapTo(top_win, QPoint(0, 0))
        w = self.width()
        h = self.height()

        if w <= 0 or h <= 0:
            return

        dest_rect = (
            top_left.x(),
            top_left.y(),
            top_left.x() + w,
            top_left.y() + h,
        )
        update_dwm_thumbnail(self._thumb_id, dest_rect, visible=True)

    def showEvent(self, event):
        super().showEvent(event)
        self.register()
        self._update_timer.start()

    def hideEvent(self, event):
        self.unregister()
        super().hideEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_timer.start()

    def moveEvent(self, event):
        super().moveEvent(event)
        self._update_timer.start()

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def closeEvent(self, event):
        self.unregister()
        super().closeEvent(event)


class DwmHoverPreviewPopup(QtWidgets.QWidget):
    """
    Popup flottant grand format affichant la prévisualisation en direct
    au survol d'une carte de personnage.
    """

    request_focus = Signal(int)

    def __init__(self, pseudo: str, classe: str, source_hwnd: int, parent=None):
        super().__init__(parent)
        self.source_hwnd = source_hwnd
        self.pseudo = pseudo
        self.classe = classe

        self.setWindowFlags(Qt.ToolTip | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFixedSize(260, 168)

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.card = QtWidgets.QFrame(objectName="dwmHoverPopup")
        card_lay = QtWidgets.QVBoxLayout(self.card)
        card_lay.setContentsMargins(8, 6, 8, 8)
        card_lay.setSpacing(6)

        # En-tête avec pseudo et classe
        hdr = QtWidgets.QHBoxLayout()
        hdr.setContentsMargins(0, 0, 0, 0)
        hdr.setSpacing(6)

        lbl_name = QtWidgets.QLabel(f"{pseudo} ({classe})")
        lbl_name.setStyleSheet("font-weight:700; font-size:11px;")
        hdr.addWidget(lbl_name)
        hdr.addStretch()

        badge_live = QtWidgets.QLabel("● EN DIRECT")
        badge_live.setStyleSheet("color:#00E676; font-size:9px; font-weight:800;")
        hdr.addWidget(badge_live)

        card_lay.addLayout(hdr)

        # Zone du flux vidéo DWM
        self.thumb = DwmThumbnailWidget(source_hwnd, self)
        self.thumb.setFixedHeight(126)
        self.thumb.clicked.connect(self._on_clicked)
        card_lay.addWidget(self.thumb)

        root.addWidget(self.card)

    def _on_clicked(self):
        self.request_focus.emit(self.source_hwnd)
        self.close()

    def show_near_widget(self, target_widget: QtWidgets.QWidget):
        """Positionne le popup intelligemment au-dessus ou en-dessous du widget cible."""
        if not target_widget:
            return

        target_geo = target_widget.frameGeometry()
        top_left = target_widget.mapToGlobal(QPoint(0, 0))

        scr = QtGui.QGuiApplication.screenAt(top_left)
        avail = scr.availableGeometry() if scr else QtCore.QRect(0, 0, 1920, 1080)

        # Préférer au-dessus si de l'espace existe
        x = top_left.x() + (target_widget.width() - self.width()) // 2
        y_above = top_left.y() - self.height() - 6
        y_below = top_left.y() + target_widget.height() + 6

        if y_above >= avail.top():
            y = y_above
        else:
            y = y_below

        # Garder à l'intérieur de l'écran horizontalement
        x = max(avail.left() + 4, min(x, avail.right() - self.width() - 4))

        self.move(x, y)
        self.show()
        self.raise_()
