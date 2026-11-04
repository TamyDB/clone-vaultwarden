"""Tela principal do cofre aberto."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget


class MainView(QWidget):
    lock_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.lock_button = QPushButton("Bloquear")
        self.lock_button.clicked.connect(self.lock_requested)

        toolbar = QHBoxLayout()
        toolbar.addStretch()
        toolbar.addWidget(self.lock_button)

        placeholder = QLabel("Cofre aberto.")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout = QVBoxLayout(self)
        layout.addLayout(toolbar)
        layout.addWidget(placeholder, stretch=1)
