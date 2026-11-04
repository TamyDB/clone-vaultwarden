"""Tela principal do cofre aberto."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QGuiApplication, QPalette
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from cofre.domain.models import DomainError
from cofre.services.vault_service import VaultService
from cofre.ui.clipboard import CLIPBOARD_CLEAR_MS, ClipboardGuard
from cofre.ui.entry_dialog import EntryDialog
from cofre.ui.labels import NO_USERNAME_LABEL
from cofre.ui.reveal_dialog import RevealDialog
from cofre.ui.workers import DISK_ERROR_MESSAGE


class MainView(QWidget):
    lock_requested = Signal()
    export_requested = Signal()
    restore_requested = Signal()

    def __init__(
        self,
        service: VaultService,
        clipboard_guard: ClipboardGuard | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._service = service
        self.clipboard_guard = clipboard_guard or ClipboardGuard(
            QGuiApplication.clipboard(), parent=self
        )
        # A tela só guarda a chave de cada linha; a senha é buscada no serviço na hora de usar.
        self._row_keys: list[tuple[str, str | None]] = []

        self.add_button = QPushButton("Adicionar")
        self.export_button = QPushButton("Exportar backup")
        self.restore_button = QPushButton("Restaurar backup")
        self.lock_button = QPushButton("Bloquear")
        self.reveal_button = QPushButton("Revelar")
        self.copy_button = QPushButton("Copiar")
        self.edit_button = QPushButton("Editar")
        self.delete_button = QPushButton("Excluir")
        self.add_button.clicked.connect(self._add_entry)
        self.lock_button.clicked.connect(self.lock_requested)
        self.export_button.clicked.connect(self.export_requested)
        self.restore_button.clicked.connect(self.restore_requested)
        self.reveal_button.clicked.connect(self._reveal)
        self.copy_button.clicked.connect(self._copy)
        self.edit_button.clicked.connect(self._edit)
        self.delete_button.clicked.connect(self._delete)

        toolbar = QHBoxLayout()
        toolbar.addWidget(self.add_button)
        toolbar.addWidget(self.export_button)
        toolbar.addWidget(self.restore_button)
        toolbar.addStretch()
        toolbar.addWidget(self.lock_button)

        # A tabela nunca recebe a senha (RN4).
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Serviço", "Usuário"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().hide()
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.itemSelectionChanged.connect(self._update_buttons)

        actions = QHBoxLayout()
        actions.addWidget(self.reveal_button)
        actions.addWidget(self.copy_button)
        actions.addWidget(self.edit_button)
        actions.addStretch()
        actions.addWidget(self.delete_button)

        self.status = QLabel(wordWrap=True)

        layout = QVBoxLayout(self)
        layout.addLayout(toolbar)
        layout.addWidget(self.table, stretch=1)
        layout.addLayout(actions)
        layout.addWidget(self.status)
        self._update_buttons()

    def refresh(self) -> None:
        entries = self._service.entries()
        self._row_keys = [(entry.service, entry.username) for entry in entries]
        self.table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            self.table.setItem(row, 0, QTableWidgetItem(entry.service))
            self.table.setItem(row, 1, self._username_item(entry.username))
        self._update_buttons()

    def clear(self) -> None:
        """Chamado ao bloquear: nada do cofre deve sobrar na tela nem na área de transferência."""
        self.table.setRowCount(0)
        self._row_keys = []
        self.status.clear()
        self.clipboard_guard.clear_if_ours()
        self._update_buttons()

    def _username_item(self, username: str | None) -> QTableWidgetItem:
        if username is not None:
            return QTableWidgetItem(username)
        # Itálico e cinza para não ser confundido com um usuário chamado "(sem usuário)".
        item = QTableWidgetItem(NO_USERNAME_LABEL)
        font = item.font()
        font.setItalic(True)
        item.setFont(font)
        item.setForeground(self.palette().color(QPalette.ColorRole.PlaceholderText))
        return item

    def _selected_key(self) -> tuple[str, str | None] | None:
        row = self.table.currentRow()
        if not self.table.selectedItems() or not 0 <= row < len(self._row_keys):
            return None
        return self._row_keys[row]

    def _update_buttons(self) -> None:
        has_selection = self._selected_key() is not None
        for button in (self.reveal_button, self.copy_button, self.edit_button, self.delete_button):
            button.setEnabled(has_selection)

    def _add_entry(self) -> None:
        dialog = EntryDialog(self._service, self)
        if dialog.exec() == EntryDialog.DialogCode.Accepted:
            self.refresh()
            self.status.clear()
        dialog.deleteLater()

    def _edit(self) -> None:
        key = self._selected_key()
        if key is None:
            return
        try:
            dialog = EntryDialog(self._service, self, editing=key)
        except DomainError as error:
            self.status.setText(str(error))
            return
        if dialog.exec() == EntryDialog.DialogCode.Accepted:
            self.refresh()
            self.status.setText("Entrada atualizada.")
        dialog.deleteLater()

    def _reveal(self) -> None:
        key = self._selected_key()
        if key is None:
            return
        try:
            password = self._service.get_password(*key)
        except DomainError as error:
            self.status.setText(str(error))
            return
        dialog = RevealDialog(key[0], key[1], password, self)
        del password
        dialog.exec()
        dialog.deleteLater()

    def _copy(self) -> None:
        key = self._selected_key()
        if key is None:
            return
        try:
            password = self._service.get_password(*key)
        except DomainError as error:
            self.status.setText(str(error))
            return
        self.clipboard_guard.copy_secret(password)
        seconds = CLIPBOARD_CLEAR_MS // 1000
        self.status.setText(f"Senha copiada. Será apagada da área de transferência em {seconds} s.")

    def _delete(self) -> None:
        key = self._selected_key()
        if key is None or not self._confirm_delete(*key):
            return
        try:
            self._service.delete_entry(*key, confirmed=True)
        except DomainError as error:
            self.status.setText(str(error))
        except OSError:
            self.status.setText(DISK_ERROR_MESSAGE)
        else:
            self.refresh()
            self.status.setText("Entrada excluída.")

    def _confirm_delete(self, service: str, username: str | None) -> bool:
        account = service if username is None else f"{service} ({username})"
        answer = QMessageBox.question(
            self,
            "Excluir entrada",
            f"Excluir a entrada {account}?\nEsta ação não pode ser desfeita.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes
