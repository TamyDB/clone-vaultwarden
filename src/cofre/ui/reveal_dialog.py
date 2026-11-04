"""Mostra a senha de uma conta, por ação explícita (RN4)."""

from __future__ import annotations

from PySide6.QtWidgets import QDialog, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget

from cofre.ui import theme
from cofre.ui.labels import NO_USERNAME_LABEL


class RevealDialog(QDialog):
    def __init__(
        self, service: str, username: str | None, password: str, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        # A senha não vai para o título nem para nenhum texto além do campo.
        self.setWindowTitle("Senha")
        self.setMinimumWidth(420)

        heading = QLabel(service)
        theme.set_role(heading, "heading")
        who = QLabel(username if username is not None else NO_USERNAME_LABEL)
        theme.set_role(who, "muted")

        # Fonte monoespaçada para distinguir caracteres parecidos, como 0 e O ou l e 1.
        self.password_field = QLineEdit(password, readOnly=True)
        self.password_field.setFont(theme.mono_font(13))
        self.close_button = QPushButton("Fechar", default=True)
        theme.set_role(self.close_button, "primary")
        self.close_button.clicked.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(6)
        layout.addWidget(heading)
        layout.addWidget(who)
        layout.addSpacing(12)
        layout.addWidget(self.password_field)
        layout.addSpacing(14)
        layout.addWidget(self.close_button)

    def done(self, result: int) -> None:
        self.password_field.clear()
        super().done(result)
