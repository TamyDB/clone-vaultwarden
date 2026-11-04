"""Diálogo de nova entrada, com senha própria ou gerada."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from cofre.domain.models import DomainError
from cofre.domain.passwords import (
    DEFAULT_GENERATED_LENGTH,
    MAX_GENERATED_LENGTH,
    MIN_GENERATED_LENGTH,
    PasswordPolicy,
    generate_password,
)
from cofre.services.vault_service import VaultService
from cofre.ui.workers import DISK_ERROR_MESSAGE


class EntryDialog(QDialog):
    def __init__(
        self,
        service: VaultService,
        parent: QWidget | None = None,
        editing: tuple[str, str | None] | None = None,
    ) -> None:
        super().__init__(parent)
        self._service = service
        self._editing = editing
        self.setWindowTitle("Editar entrada" if editing else "Nova entrada")

        self.service_field = QLineEdit()
        self.username_field = QLineEdit()
        self.has_username = QCheckBox("Esta conta tem usuário", checked=True)
        self.password_field = QLineEdit(echoMode=QLineEdit.EchoMode.Password)
        self.show_button = QPushButton("Mostrar", checkable=True, autoDefault=False)
        self.length_field = QSpinBox(
            minimum=MIN_GENERATED_LENGTH,
            maximum=MAX_GENERATED_LENGTH,
            value=DEFAULT_GENERATED_LENGTH,
        )
        self.lowercase = QCheckBox("a-z", checked=True)
        self.uppercase = QCheckBox("A-Z", checked=True)
        self.digits = QCheckBox("0-9", checked=True)
        self.symbols = QCheckBox("Símbolos", checked=True)
        self.generate_button = QPushButton("Gerar senha", autoDefault=False)
        self.message = QLabel(wordWrap=True)
        self.cancel_button = QPushButton("Cancelar", autoDefault=False)
        self.save_button = QPushButton("Salvar", default=True)

        password_row = QHBoxLayout()
        password_row.addWidget(self.password_field)
        password_row.addWidget(self.show_button)

        classes_row = QHBoxLayout()
        for checkbox in (self.lowercase, self.uppercase, self.digits, self.symbols):
            classes_row.addWidget(checkbox)

        generator_row = QHBoxLayout()
        generator_row.addWidget(QLabel("Tamanho"))
        generator_row.addWidget(self.length_field)
        generator_row.addStretch()
        generator_row.addWidget(self.generate_button)

        form = QFormLayout()
        form.addRow("Serviço", self.service_field)
        form.addRow("Usuário", self.username_field)
        form.addRow(self.has_username)
        form.addRow("Senha", password_row)
        form.addRow("Incluir", classes_row)
        form.addRow(generator_row)

        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(self.cancel_button)
        buttons.addWidget(self.save_button)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.message)
        layout.addLayout(buttons)

        self.has_username.toggled.connect(self.username_field.setEnabled)
        self.show_button.toggled.connect(self._toggle_password)
        self.generate_button.clicked.connect(self._generate)
        self.cancel_button.clicked.connect(self.reject)
        self.save_button.clicked.connect(self._save)
        if editing is not None:
            self._load(*editing)

    def _load(self, service_name: str, username: str | None) -> None:
        password = self._service.get_password(service_name, username)
        self.service_field.setText(service_name)
        self.has_username.setChecked(username is not None)
        self.username_field.setText(username or "")
        self.password_field.setText(password)

    def done(self, result: int) -> None:
        # Ao editar, a senha atual está no campo: não deve sobrar nele depois de fechar.
        self.password_field.clear()
        super().done(result)

    def _toggle_password(self, visible: bool) -> None:
        self.password_field.setEchoMode(
            QLineEdit.EchoMode.Normal if visible else QLineEdit.EchoMode.Password
        )
        self.show_button.setText("Ocultar" if visible else "Mostrar")

    def _generate(self) -> None:
        try:
            policy = PasswordPolicy(
                length=self.length_field.value(),
                lowercase=self.lowercase.isChecked(),
                uppercase=self.uppercase.isChecked(),
                digits=self.digits.isChecked(),
                symbols=self.symbols.isChecked(),
            )
        except DomainError as error:
            self.message.setText(str(error))
            return
        self.password_field.setText(generate_password(policy))
        self.message.clear()

    def _persist(self, username: str | None) -> None:
        name, password = self.service_field.text(), self.password_field.text()
        if self._editing is None:
            self._service.add_entry(name, username, password)
        else:
            self._service.update_entry(*self._editing, name, username, password)

    def _save(self) -> None:
        username = self.username_field.text() if self.has_username.isChecked() else None
        try:
            self._persist(username)
        except DomainError as error:
            self.message.setText(str(error))
        except OSError:
            self.message.setText(DISK_ERROR_MESSAGE)
        else:
            self.accept()
