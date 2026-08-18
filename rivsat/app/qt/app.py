"""
RivSat desktop bootstrap — QApplication, splash screen, main window.

Entry points:
    python -m rivsat.app     (see rivsat/app/__main__.py)
    rivsat-gui               (console_script → rivsat.app.qt.app:main)
"""
import sys
import os

# QtWebEngine MUST be imported before QApplication is constructed.
from PyQt6.QtWebEngineWidgets import QWebEngineView  # noqa: F401
from PyQt6.QtWidgets import QApplication, QSplashScreen, QLabel
from PyQt6.QtGui import QPixmap, QPainter, QColor, QFont
from PyQt6.QtCore import Qt, QTimer

from rivsat.app.qt.theme import QSS, COLORS, apply_mpl_style


def _make_splash() -> QSplashScreen:
    """Draw a simple branded splash pixmap (no external image needed)."""
    pm = QPixmap(560, 320)
    pm.fill(QColor(COLORS["navy"]))
    p = QPainter(pm)
    p.setPen(QColor("#ffffff"))
    p.setFont(QFont("Segoe UI", 34, QFont.Weight.Bold))
    p.drawText(pm.rect().adjusted(0, -40, 0, -40),
               Qt.AlignmentFlag.AlignCenter, "RivSat")
    p.setFont(QFont("Segoe UI", 12))
    p.setPen(QColor("#9fb3c8"))
    p.drawText(pm.rect().adjusted(0, 60, 0, 60), Qt.AlignmentFlag.AlignCenter,
               "Satellite Water Quality Platform")
    p.setFont(QFont("Segoe UI", 9))
    p.setPen(QColor("#6b8299"))
    p.drawText(pm.rect().adjusted(0, 120, 0, -18),
               Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter,
               "Loading modules…  Sentinel-2 · Landsat 8/9 · Earth Engine")
    p.end()
    return QSplashScreen(pm)


def main():
    # High-DPI friendliness
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")

    app = QApplication(sys.argv)
    app.setApplicationName("RivSat")
    app.setOrganizationName("RivSat")
    app.setStyleSheet(QSS)
    apply_mpl_style()

    splash = _make_splash()
    splash.show()
    app.processEvents()

    # Build the (heavy) main window while the splash is visible
    from rivsat.app.qt.main_window import MainWindow
    win = MainWindow()

    def _reveal():
        win.show()
        splash.finish(win)

    QTimer.singleShot(600, _reveal)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
