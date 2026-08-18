"""
Inline SVG icon set rendered to QIcon via QtSvg — no external image files.

Usage:
    from rivsat.app.qt.icons import icon
    btn.setIcon(icon("polygon"))
"""
from functools import lru_cache
from PyQt6.QtCore import Qt, QByteArray, QSize
from PyQt6.QtGui import QIcon, QPixmap, QPainter
from PyQt6.QtSvg import QSvgRenderer

from rivsat.app.qt.theme import COLORS

# 24×24 line icons, {stroke} placeholder filled at render time.
_SVG = {
    "polygon":   '<polygon points="4,7 12,3 20,8 17,20 7,19" fill="none" stroke="{s}" stroke-width="2" stroke-linejoin="round"/>',
    "rectangle": '<rect x="4" y="6" width="16" height="12" rx="1" fill="none" stroke="{s}" stroke-width="2"/>',
    "line":      '<polyline points="4,18 10,8 15,14 20,5" fill="none" stroke="{s}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
    "point":     '<circle cx="12" cy="10" r="4" fill="{s}"/><path d="M12 14 L12 21" stroke="{s}" stroke-width="2"/>',
    "edit":      '<path d="M4 20 L4 16 L15 5 L19 9 L8 20 Z" fill="none" stroke="{s}" stroke-width="2" stroke-linejoin="round"/><path d="M13 7 L17 11" stroke="{s}" stroke-width="2"/>',
    "move":      '<path d="M12 3 L12 21 M3 12 L21 12" stroke="{s}" stroke-width="2"/><path d="M12 3 L9 6 M12 3 L15 6 M12 21 L9 18 M12 21 L15 18 M3 12 L6 9 M3 12 L6 15 M21 12 L18 9 M21 12 L18 15" stroke="{s}" stroke-width="2" fill="none"/>',
    "delete":    '<path d="M6 7 L18 7 M9 7 L9 5 L15 5 L15 7 M7 7 L8 20 L16 20 L17 7" fill="none" stroke="{s}" stroke-width="2" stroke-linejoin="round"/>',
    "zoom":      '<circle cx="10" cy="10" r="6" fill="none" stroke="{s}" stroke-width="2"/><path d="M14.5 14.5 L20 20" stroke="{s}" stroke-width="2" stroke-linecap="round"/>',
    "load":      '<path d="M4 7 L10 7 L12 9 L20 9 L20 19 L4 19 Z" fill="none" stroke="{s}" stroke-width="2" stroke-linejoin="round"/>',
    "save":      '<path d="M5 5 L16 5 L19 8 L19 19 L5 19 Z" fill="none" stroke="{s}" stroke-width="2" stroke-linejoin="round"/><rect x="8" y="5" width="7" height="5" fill="{s}"/><rect x="8" y="13" width="8" height="6" fill="none" stroke="{s}" stroke-width="1.5"/>',
    "search":    '<circle cx="10" cy="10" r="6" fill="none" stroke="{s}" stroke-width="2"/><path d="M14.5 14.5 L20 20" stroke="{s}" stroke-width="2" stroke-linecap="round"/>',
    "layers":    '<path d="M12 3 L21 8 L12 13 L3 8 Z" fill="none" stroke="{s}" stroke-width="2" stroke-linejoin="round"/><path d="M3 12 L12 17 L21 12" fill="none" stroke="{s}" stroke-width="2" stroke-linejoin="round"/>',
    "basemap":   '<rect x="3" y="5" width="18" height="14" rx="1" fill="none" stroke="{s}" stroke-width="2"/><path d="M3 10 L21 10 M9 5 L9 19 M15 5 L15 19" stroke="{s}" stroke-width="1.4"/>',
    "run":       '<polygon points="7,5 19,12 7,19" fill="{s}"/>',
    "target":    '<circle cx="12" cy="12" r="7" fill="none" stroke="{s}" stroke-width="2"/><circle cx="12" cy="12" r="2" fill="{s}"/>',
    "clear":     '<circle cx="12" cy="12" r="8" fill="none" stroke="{s}" stroke-width="2"/><path d="M8 8 L16 16 M16 8 L8 16" stroke="{s}" stroke-width="2"/>',
}


@lru_cache(maxsize=256)
def icon(name: str, color: str = None, size: int = 24) -> QIcon:
    body = _SVG.get(name)
    if body is None:
        return QIcon()
    stroke = color or COLORS["text"]
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
           f'viewBox="0 0 24 24">{body.format(s=stroke)}</svg>')
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    renderer.render(p)
    p.end()
    return QIcon(pm)
