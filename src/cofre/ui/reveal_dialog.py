"""Mostra a senha de uma entrada, por ação explícita (RN4)."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from cofre.ui.labels import NO_USERNAME_LABEL


class RevealDialog(QDialog):
    def __init__(
        self, service: str, username: str | None, password: str, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        # A senha não vai para o título nem para nenhum texto além do campo.
        self.setWindowTitle("Senha")

        self.password_field = QLineEdit(password, readOnly=True)
        self.password_field.setMinimumWidth(280)
        self.close_button = QPushButton("Fechar", default=True)
        self.close_button.clicked.connect(self.accept)

        form = QFormLayout()
        form.addRow("Serviço", QLabel(service))
        form.addRow("Usuário", QLabel(username if username is not None else NO_USERNAME_LABEL))
        form.addRow("Senha", self.password_field)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.close_button)

    def done(self, result: int) -> None:
        self.password_field.clear()
        super().done(result)
