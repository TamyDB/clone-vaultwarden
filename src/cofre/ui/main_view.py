"""Tela principal do cofre aberto."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from cofre.services.vault_service import VaultService
from cofre.ui.entry_dialog import EntryDialog

NO_USERNAME_LABEL = "(sem usuário)"


class MainView(QWidget):
    lock_requested = Signal()

    def __init__(self, service: VaultService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._service = service
        self.add_button = QPushButton("Adicionar")
        self.lock_button = QPushButton("Bloquear")
        self.add_button.clicked.connect(self._add_entry)
        self.lock_button.clicked.connect(self.lock_requested)

        toolbar = QHBoxLayout()
        toolbar.addWidget(self.add_button)
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

        layout = QVBoxLayout(self)
        layout.addLayout(toolbar)
        layout.addWidget(self.table, stretch=1)

    def refresh(self) -> None:
        entries = self._service.entries()
        self.table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            self.table.setItem(row, 0, QTableWidgetItem(entry.service))
            self.table.setItem(row, 1, self._username_item(entry.username))

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

    def clear(self) -> None:
        self.table.setRowCount(0)

    def _add_entry(self) -> None:
        dialog = EntryDialog(self._service, self)
        if dialog.exec() == EntryDialog.DialogCode.Accepted:
            self.refresh()
        dialog.deleteLater()
