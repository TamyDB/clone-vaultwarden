"""Tela inicial: cria o cofre no primeiro uso ou pede a senha mestra."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from cofre.services.vault_service import VaultService
from cofre.ui import theme
from cofre.ui.vault_mark import VaultMark
from cofre.ui.workers import TaskRunner

COLUMN_WIDTH = 360
CREATE_HINT = (
    "Escolha uma senha mestra com 12 ou mais caracteres.\nEla protege todas as suas contas."
)
OPEN_HINT = "Digite a senha mestra para abrir as suas contas."


class UnlockView(QWidget):
    unlocked = Signal()
    restore_requested = Signal()

    def __init__(self, service: VaultService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._service = service
        self._creating = False
        self._runner = TaskRunner(self)
        self._runner.succeeded.connect(self._on_succeeded)
        self._runner.failed.connect(self._on_failed)

        self.mark = VaultMark()
        self.title = QLabel()
        theme.set_role(self.title, "title")
        self.hint = QLabel(wordWrap=True)
        theme.set_role(self.hint, "muted")
        for label in (self.title, self.hint):
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.password = QLineEdit(echoMode=QLineEdit.EchoMode.Password)
        self.confirmation = QLineEdit(echoMode=QLineEdit.EchoMode.Password)
        self.show_button = QPushButton("Mostrar", checkable=True, autoDefault=False)
        self.acknowledgement = QCheckBox(
            "Entendo que, sem a senha mestra,\nos dados não podem ser recuperados."
        )
        self.message = QLabel(wordWrap=True)
        self.message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.submit = QPushButton(default=True)
        theme.set_role(self.submit, "primary")
        self.restore_button = QPushButton("Restaurar backup…", autoDefault=False)
        theme.set_role(self.restore_button, "ghost")

        password_row = QHBoxLayout()
        password_row.setSpacing(8)
        password_row.addWidget(self.password, stretch=1)
        password_row.addWidget(self.show_button)

        self._form = QFormLayout()
        self._form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        self._form.setVerticalSpacing(6)
        self._form.addRow("Senha mestra", password_row)
        self._form.addRow("Confirmar senha", self.confirmation)
        self._form.addRow(self.acknowledgement)

        column = QWidget()
        column.setFixedWidth(COLUMN_WIDTH)
        column_layout = QVBoxLayout(column)
        column_layout.setContentsMargins(0, 0, 0, 0)
        column_layout.setSpacing(14)
        column_layout.addWidget(self.mark, alignment=Qt.AlignmentFlag.AlignHCenter)
        column_layout.addWidget(self.title)
        column_layout.addWidget(self.hint)
        column_layout.addSpacing(6)
        column_layout.addLayout(self._form)
        column_layout.addWidget(self.submit)
        column_layout.addWidget(self.restore_button)
        column_layout.addWidget(self.message)

        layout = QVBoxLayout(self)
        layout.addStretch(1)
        layout.addWidget(column, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch(2)

        self.password.returnPressed.connect(self._submit)
        self.confirmation.returnPressed.connect(self._submit)
        self.submit.clicked.connect(self._submit)
        self.show_button.toggled.connect(self._toggle_visibility)
        self.restore_button.clicked.connect(self.restore_requested)
        self.reset()

    def reset(self, notice: str = "") -> None:
        """Volta ao estado inicial, sem restos de senha nos campos."""
        self._creating = not self._service.vault_exists
        self.title.setText("Criar cofre" if self._creating else "Abrir cofre")
        self.hint.setText(CREATE_HINT if self._creating else OPEN_HINT)
        self.submit.setText("Criar cofre" if self._creating else "Abrir")
        self._form.setRowVisible(self.confirmation, self._creating)
        self._form.setRowVisible(self.acknowledgement, self._creating)
        self._clear_secrets()
        self.show_button.setChecked(False)
        self.acknowledgement.setChecked(False)
        self.show_message(notice)
        self._set_busy(False)
        self.password.setFocus()

    def show_message(self, text: str, *, error: bool = False) -> None:
        self.message.setText(text)
        theme.set_kind(self.message, "error" if error else "")

    def _toggle_visibility(self, visible: bool) -> None:
        mode = QLineEdit.EchoMode.Normal if visible else QLineEdit.EchoMode.Password
        self.password.setEchoMode(mode)
        self.confirmation.setEchoMode(mode)
        self.show_button.setText("Ocultar" if visible else "Mostrar")

    def _submit(self) -> None:
        if not self.submit.isEnabled():
            return
        master_password = self.password.text()
        if self._creating:
            confirmation = self.confirmation.text()
            acknowledged = self.acknowledgement.isChecked()
            task = lambda: self._service.create(  # noqa: E731
                master_password, confirmation, acknowledged_no_recovery=acknowledged
            )
            self.show_message("Criando o cofre…")
        else:
            task = lambda: self._service.unlock(master_password)  # noqa: E731
            self.show_message("Abrindo o cofre…")
        self._set_busy(True)
        self._runner.start(task)

    def _on_succeeded(self) -> None:
        self.reset()
        self.unlocked.emit()

    def _on_failed(self, message: str) -> None:
        self._clear_secrets()
        self._set_busy(False)
        self.show_message(message, error=True)
        self.password.setFocus()

    def _clear_secrets(self) -> None:
        self.password.clear()
        self.confirmation.clear()

    def _set_busy(self, busy: bool) -> None:
        for widget in (
            self.password,
            self.confirmation,
            self.show_button,
            self.acknowledgement,
            self.submit,
            self.restore_button,
        ):
            widget.setEnabled(not busy)
