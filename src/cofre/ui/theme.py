"""Aparência do aplicativo: paletas clara e escura, folha de estilo Qt e fontes.

A paleta segue o esquema de cores do sistema. O latão fica reservado ao foco do teclado e ao
mostrador do cofre, para continuar funcionando como sinal.
"""

from __future__ import annotations

from dataclasses import dataclass
from string import Template

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication, QWidget

UI_FONTS = ["Inter", "Segoe UI", "Noto Sans", "Cantarell", "DejaVu Sans", "Arial"]
MONO_FONTS = [
    "Cascadia Mono",
    "JetBrains Mono",
    "DejaVu Sans Mono",
    "Consolas",
    "Menlo",
    "Courier New",
]
BASE_POINT_SIZE = 10.5


@dataclass(frozen=True, slots=True)
class Colors:
    background: str
    surface: str
    ink: str
    muted: str
    border: str
    field_border: str
    hover: str
    selection: str
    primary: str
    primary_hover: str
    on_primary: str
    accent: str
    danger: str


LIGHT = Colors(
    background="#EDF0EC",
    surface="#FBFCFA",
    ink="#1F2B27",
    muted="#5A6762",
    border="#C5CEC8",
    field_border="#7F8C86",
    hover="#E2E8E4",
    selection="#D3E4DB",
    primary="#2D5B4E",
    primary_hover="#244C41",
    on_primary="#FFFFFF",
    accent="#A8761F",
    danger="#A63A32",
)

DARK = Colors(
    background="#131A18",
    surface="#1A2421",
    ink="#E4EBE7",
    muted="#9AA8A2",
    border="#2F3D38",
    field_border="#6E7F78",
    hover="#22302C",
    selection="#26403A",
    primary="#5FA891",
    primary_hover="#74B8A2",
    on_primary="#0E1513",
    accent="#D9A441",
    danger="#E08A82",
)

_current = LIGHT

STYLESHEET = Template(
    """
QMainWindow, QDialog { background: $background; }
QLabel { background: transparent; }
QLabel[role="title"] { font-size: 20pt; font-weight: 600; }
QLabel[role="heading"] { font-size: 14pt; font-weight: 600; }
QLabel[role="muted"] { color: $muted; }
QLabel[kind="error"] { color: $danger; }

QLineEdit {
    background: $surface; border: 1px solid $field_border; border-radius: 6px;
    padding: 8px 10px; selection-background-color: $selection; selection-color: $ink;
}
QLineEdit:focus { border: 2px solid $accent; padding: 7px 9px; }
QLineEdit:disabled { background: $background; color: $muted; }
QLineEdit[role="secret"] { font-size: 13pt; }

QPushButton, QToolButton {
    background: $surface; border: 1px solid $border; border-radius: 6px;
    padding: 8px 16px; min-height: 18px;
}
QPushButton:hover, QToolButton:hover { background: $hover; }
QPushButton:checked, QToolButton:checked { background: $selection; }
QPushButton:focus, QToolButton:focus { border: 2px solid $accent; padding: 7px 15px; }
QPushButton:disabled, QToolButton:disabled { background: $background; color: $muted; }
QPushButton::menu-indicator { subcontrol-position: right center; right: 10px; }
QPushButton[hasMenu="true"] { padding-right: 30px; }
QPushButton[hasMenu="true"]:focus { padding-right: 29px; }

QPushButton[role="primary"] {
    background: $primary; color: $on_primary; border: 1px solid $primary; font-weight: 600;
}
QPushButton[role="primary"]:hover { background: $primary_hover; border-color: $primary_hover; }
QPushButton[role="primary"]:focus { border: 2px solid $accent; }
QPushButton[role="primary"]:disabled { background: $border; color: $muted; border-color: $border; }

QPushButton[role="ghost"], QToolButton[role="ghost"] {
    background: transparent; border: 1px solid transparent;
}
QPushButton[role="ghost"]:hover, QToolButton[role="ghost"]:hover { background: $hover; }
QPushButton[role="ghost"]:focus, QToolButton[role="ghost"]:focus { border: 2px solid $accent; }
QPushButton[role="ghost"]:disabled { background: transparent; color: $muted; }
QPushButton[role="danger"] { color: $danger; }
QPushButton[role="danger"]:disabled { color: $muted; }

QTableWidget {
    background: $surface; border: 1px solid $border; border-radius: 8px;
    gridline-color: transparent; outline: 0;
}
QTableWidget::item { padding: 4px 14px; border: none; }
QTableWidget::item:hover { background: $hover; }
QTableWidget::item:selected { background: $selection; color: $ink; }
QHeaderView { background: transparent; }
QHeaderView::section {
    background: $surface; color: $muted; border: none; border-bottom: 1px solid $border;
    padding: 10px 17px; font-weight: 600;
}
QTableCornerButton::section { background: $surface; border: none; }

QMenu { background: $surface; border: 1px solid $border; border-radius: 8px; padding: 6px; }
QMenu::item { padding: 8px 24px 8px 14px; border-radius: 4px; }
QMenu::item:selected { background: $selection; color: $ink; }
QMenu::separator { height: 1px; background: $border; margin: 6px 8px; }

QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: $border; border-radius: 3px; min-height: 28px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
"""
)


def colors() -> Colors:
    return _current


def build_stylesheet(palette: Colors) -> str:
    return STYLESHEET.substitute(_as_dict(palette))


def _as_dict(palette: Colors) -> dict[str, str]:
    return {name: getattr(palette, name) for name in palette.__slots__}


def mono_font(point_size: float = BASE_POINT_SIZE) -> QFont:
    font = QFont()
    font.setFamilies(MONO_FONTS)
    font.setStyleHint(QFont.StyleHint.Monospace)
    font.setPointSizeF(point_size)
    return font


def set_kind(widget: QWidget, kind: str) -> None:
    """Muda a aparência de um texto (por exemplo, "error") e força o Qt a reaplicar o estilo."""
    widget.setProperty("kind", kind)
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)


def set_role(widget: QWidget, role: str) -> QWidget:
    widget.setProperty("role", role)
    return widget


def _qt_palette(scheme: Colors) -> QPalette:
    palette = QPalette()
    roles = {
        QPalette.ColorRole.Window: scheme.background,
        QPalette.ColorRole.WindowText: scheme.ink,
        QPalette.ColorRole.Base: scheme.surface,
        QPalette.ColorRole.AlternateBase: scheme.background,
        QPalette.ColorRole.Text: scheme.ink,
        QPalette.ColorRole.Button: scheme.surface,
        QPalette.ColorRole.ButtonText: scheme.ink,
        QPalette.ColorRole.ToolTipBase: scheme.surface,
        QPalette.ColorRole.ToolTipText: scheme.ink,
        QPalette.ColorRole.PlaceholderText: scheme.muted,
        QPalette.ColorRole.Highlight: scheme.primary,
        QPalette.ColorRole.HighlightedText: scheme.on_primary,
        QPalette.ColorRole.Link: scheme.primary,
        QPalette.ColorRole.Mid: scheme.border,
        QPalette.ColorRole.Dark: scheme.border,
    }
    for role, value in roles.items():
        palette.setColor(role, QColor(value))
    for role in (
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.Text,
        QPalette.ColorRole.ButtonText,
    ):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor(scheme.muted))
    return palette


def apply_scheme(app: QApplication, scheme: Colors) -> None:
    global _current
    _current = scheme
    app.setPalette(_qt_palette(scheme))
    app.setStyleSheet(build_stylesheet(scheme))


def apply(app: QApplication) -> None:
    """Aplica o tema (Fusion, para o QSS se comportar igual no Windows e no Linux) e o mantém
    em sincronia com o esquema de cores do sistema."""
    app.setStyle("Fusion")
    font = QFont()
    font.setFamilies(UI_FONTS)
    font.setPointSizeF(BASE_POINT_SIZE)
    app.setFont(font)

    def follow_system(*_args: object) -> None:
        dark = app.styleHints().colorScheme() == Qt.ColorScheme.Dark
        apply_scheme(app, DARK if dark else LIGHT)

    app.styleHints().colorSchemeChanged.connect(follow_system)
    follow_system()


__all__ = [
    "DARK",
    "LIGHT",
    "Colors",
    "apply",
    "apply_scheme",
    "build_stylesheet",
    "colors",
    "mono_font",
    "set_kind",
    "set_role",
]
