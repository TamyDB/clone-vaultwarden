"""Mostrador de cofre desenhado em código: a marca do aplicativo na tela de desbloqueio."""

from __future__ import annotations

import math

from PySide6.QtCore import QEvent, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QWidget

from cofre.ui import theme

TICKS = 24


class VaultMark(QWidget):
    def __init__(self, size: int = 76, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(size, size)
        # Decorativo: leitores de tela e o foco do teclado não precisam passar por ele.
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802
        if event.type() == QEvent.Type.PaletteChange:
            self.update()
        super().changeEvent(event)

    def paintEvent(self, _event: QEvent) -> None:  # noqa: N802
        colors = theme.colors()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        center = QPointF(self.width() / 2, self.height() / 2)
        radius = min(self.width(), self.height()) / 2 - 3

        painter.setPen(QPen(QColor(colors.border), 2))
        painter.setBrush(QColor(colors.surface))
        painter.drawEllipse(center, radius, radius)

        for index in range(TICKS):
            angle = 2 * math.pi * index / TICKS
            major = index % 6 == 0
            outer, inner = radius - 5, radius - (13 if major else 9)
            tick_pen = QPen(QColor(colors.muted), 2 if major else 1.2)
            tick_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(tick_pen)
            painter.drawLine(
                QPointF(center.x() + inner * math.sin(angle), center.y() - inner * math.cos(angle)),
                QPointF(center.x() + outer * math.sin(angle), center.y() - outer * math.cos(angle)),
            )

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(colors.primary))
        painter.drawEllipse(center, radius * 0.5, radius * 0.5)

        # Fechadura: um círculo e uma fenda, na cor do texto sobre o botão principal.
        painter.setBrush(QColor(colors.on_primary))
        hole = QPointF(center.x(), center.y() - radius * 0.07)
        painter.drawEllipse(hole, radius * 0.1, radius * 0.1)
        slot_width, slot_height = radius * 0.08, radius * 0.2
        slot_top = center.y() - radius * 0.02
        painter.drawRoundedRect(
            QRectF(center.x() - slot_width / 2, slot_top, slot_width, slot_height),
            1.5,
            1.5,
        )

        # Ponteiro de latão no topo do mostrador.
        painter.setBrush(QColor(colors.accent))
        painter.drawPolygon(
            QPolygonF(
                [
                    QPointF(center.x() - 5, center.y() - radius - 1),
                    QPointF(center.x() + 5, center.y() - radius - 1),
                    QPointF(center.x(), center.y() - radius + 8),
                ]
            )
        )
