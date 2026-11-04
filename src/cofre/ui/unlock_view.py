"""Tela inicial: cria o cofre no primeiro uso ou pede a senha mestra."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from cofre.services.vault_service import VaultService
from cofre.ui.workers import TaskRunner


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

        self.title = QLabel()
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.password = QLineEdit(echoMode=QLineEdit.EchoMode.Password)
        self.confirmation = QLineEdit(echoMode=QLineEdit.EchoMode.Password)
        self.acknowledgement = QCheckBox(
            "Entendo que, se eu esquecer a senha mestra,\nos dados não poderão ser recuperados."
        )
        self.message = QLabel(wordWrap=True)
        self.message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.submit = QPushButton()
        self.restore_button = QPushButton("Restaurar backup…")

        self._form = QFormLayout()
        self._form.addRow("Senha mestra", self.password)
        self._form.addRow("Confirmação", self.confirmation)
        self._form.addRow(self.acknowledgement)

        layout = QVBoxLayout(self)
        layout.addStretch()
        layout.addWidget(self.title)
        layout.addLayout(self._form)
        layout.addWidget(self.submit)
        layout.addWidget(self.restore_button)
        layout.addWidget(self.message)
        layout.addStretch()

        self.password.returnPressed.connect(self._submit)
        self.confirmation.returnPressed.connect(self._submit)
        self.submit.clicked.connect(self._submit)
        self.restore_button.clicked.connect(self.restore_requested)
        self.reset()

    def reset(self, notice: str = "") -> None:
        """Volta ao estado inicial, sem restos de senha nos campos."""
        self._creating = not self._service.vault_exists
        self.title.setText("Criar novo cofre" if self._creating else "Abrir cofre")
        self.submit.setText("Criar cofre" if self._creating else "Abrir")
        self._form.setRowVisible(self.confirmation, self._creating)
        self._form.setRowVisible(self.acknowledgement, self._creating)
        self._clear_secrets()
        self.acknowledgement.setChecked(False)
        self.message.setText(notice)
        self._set_busy(False)
        self.password.setFocus()

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
            self.message.setText("Criando o cofre…")
        else:
            task = lambda: self._service.unlock(master_password)  # noqa: E731
            self.message.setText("Abrindo o cofre…")
        self._set_busy(True)
        self._runner.start(task)

    def _on_succeeded(self) -> None:
        self.reset()
        self.unlocked.emit()

    def _on_failed(self, message: str) -> None:
        self._clear_secrets()
        self._set_busy(False)
        self.message.setText(message)
        self.password.setFocus()

    def _clear_secrets(self) -> None:
        self.password.clear()
        self.confirmation.clear()

    def _set_busy(self, busy: bool) -> None:
        for widget in (
            self.password,
            self.confirmation,
            self.acknowledgement,
            self.submit,
            self.restore_button,
        ):
            widget.setEnabled(not busy)
