"""Tela principal do cofre aberto."""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QGuiApplication, QPalette
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from cofre.domain.models import DomainError
from cofre.services.vault_service import VaultService
from cofre.ui import theme
from cofre.ui.clipboard import CLIPBOARD_CLEAR_MS, ClipboardGuard
from cofre.ui.entry_dialog import EntryDialog
from cofre.ui.labels import NO_USERNAME_LABEL
from cofre.ui.reveal_dialog import RevealDialog
from cofre.ui.workers import DISK_ERROR_MESSAGE

ROW_HEIGHT = 46
SELECT_HINT = "Selecione uma conta."
EMPTY_TITLE = "Nenhuma conta ainda"
EMPTY_TEXT = "Guarde a primeira senha aqui.\nTudo fica criptografado neste computador."


def count_label(total: int) -> str:
    if total == 0:
        return "Nenhuma conta"
    return "1 conta" if total == 1 else f"{total} contas"


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

        self._build_header()
        self._build_content()
        self._build_actions()

        self.status = QLabel(wordWrap=True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 20)
        layout.setSpacing(16)
        layout.addLayout(self._header)
        layout.addWidget(self.content, stretch=1)
        layout.addLayout(self._actions)
        layout.addWidget(self.status)
        self._update_buttons()

    def _build_header(self) -> None:
        self.title = QLabel("Contas")
        theme.set_role(self.title, "title")
        self.count = QLabel()
        theme.set_role(self.count, "muted")

        self.add_button = QPushButton("Nova conta")
        theme.set_role(self.add_button, "primary")
        self.lock_button = QPushButton("Bloquear")

        self.backup_button = QPushButton("Backup")
        self.backup_button.setProperty("hasMenu", True)
        backup_menu = QMenu(self.backup_button)
        self.export_action = backup_menu.addAction("Exportar backup…")
        self.restore_action = backup_menu.addAction("Restaurar backup…")
        self.backup_button.setMenu(backup_menu)

        self.add_button.clicked.connect(self._add_entry)
        self.lock_button.clicked.connect(self.lock_requested)
        self.export_action.triggered.connect(self.export_requested)
        self.restore_action.triggered.connect(self.restore_requested)

        titles = QVBoxLayout()
        titles.setSpacing(2)
        titles.addWidget(self.title)
        titles.addWidget(self.count)

        self._header = QHBoxLayout()
        self._header.setSpacing(10)
        self._header.addLayout(titles)
        self._header.addStretch()
        self._header.addWidget(self.backup_button)
        self._header.addWidget(self.lock_button)
        self._header.addWidget(self.add_button)

    def _build_content(self) -> None:
        # A tabela nunca recebe a senha (RN4).
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Serviço", "Usuário"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setHighlightSections(False)
        self.table.horizontalHeader().setDefaultAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(ROW_HEIGHT)
        self.table.setShowGrid(False)
        self.table.setFrameShape(QTableWidget.Shape.NoFrame)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.itemSelectionChanged.connect(self._update_buttons)
        self.table.customContextMenuRequested.connect(self._show_context_menu)

        self.empty_add_button = QPushButton("Nova conta")
        theme.set_role(self.empty_add_button, "primary")
        self.empty_add_button.clicked.connect(self._add_entry)
        empty_title = QLabel(EMPTY_TITLE)
        theme.set_role(empty_title, "heading")
        empty_text = QLabel(EMPTY_TEXT)
        theme.set_role(empty_text, "muted")
        for label in (empty_title, empty_text):
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.empty_state = QWidget()
        empty_layout = QVBoxLayout(self.empty_state)
        empty_layout.setSpacing(8)
        empty_layout.addStretch(1)
        empty_layout.addWidget(empty_title)
        empty_layout.addWidget(empty_text)
        empty_layout.addSpacing(10)
        empty_layout.addWidget(self.empty_add_button, alignment=Qt.AlignmentFlag.AlignHCenter)
        empty_layout.addStretch(2)

        self.content = QStackedWidget()
        self.content.addWidget(self.table)
        self.content.addWidget(self.empty_state)

    def _build_actions(self) -> None:
        self.copy_button = QPushButton("Copiar senha")
        self.reveal_button = QPushButton("Revelar")
        self.edit_button = QPushButton("Editar")
        self.delete_button = QPushButton("Excluir")
        theme.set_role(self.delete_button, "danger")
        self.hint = QLabel(SELECT_HINT)
        theme.set_role(self.hint, "muted")

        self.copy_button.clicked.connect(self._copy)
        self.reveal_button.clicked.connect(self._reveal)
        self.edit_button.clicked.connect(self._edit)
        self.delete_button.clicked.connect(self._delete)

        self._actions = QHBoxLayout()
        self._actions.setSpacing(8)
        self._actions.addWidget(self.copy_button)
        self._actions.addWidget(self.reveal_button)
        self._actions.addWidget(self.edit_button)
        self._actions.addWidget(self.hint)
        self._actions.addStretch()
        self._actions.addWidget(self.delete_button)

    def focus_list(self) -> None:
        """Leva o foco ao que o usuário provavelmente quer: a lista, ou criar a primeira conta."""
        (self.table if self._row_keys else self.empty_add_button).setFocus()

    def refresh(self) -> None:
        entries = self._service.entries()
        self._row_keys = [(entry.service, entry.username) for entry in entries]
        self.table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            self.table.setItem(row, 0, QTableWidgetItem(entry.service))
            self.table.setItem(row, 1, self._username_item(entry.username))
        self.count.setText(count_label(len(entries)))
        self._update_buttons()

    def clear(self) -> None:
        """Chamado ao bloquear: nada do cofre deve sobrar na tela nem na área de transferência."""
        self.table.setRowCount(0)
        self._row_keys = []
        self.count.clear()
        self.show_status("")
        self.clipboard_guard.clear_if_ours()
        self._update_buttons()

    def show_status(self, text: str, *, error: bool = False) -> None:
        self.status.setText(text)
        theme.set_kind(self.status, "error" if error else "")

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
        has_rows = bool(self._row_keys)
        has_selection = self._selected_key() is not None
        for button in (self.reveal_button, self.copy_button, self.edit_button, self.delete_button):
            button.setEnabled(has_selection)
        self.content.setCurrentWidget(self.table if has_rows else self.empty_state)
        # No estado vazio, o chamado para criar a primeira conta fica no centro da tela.
        self.add_button.setVisible(has_rows)
        for widget in (self.copy_button, self.reveal_button, self.edit_button, self.delete_button):
            widget.setVisible(has_rows)
        self.hint.setVisible(has_rows and not has_selection)

    def _show_context_menu(self, position: QPoint) -> None:
        item = self.table.itemAt(position)
        if item is None:
            return
        self.table.selectRow(item.row())
        menu = QMenu(self)
        menu.addAction("Copiar senha", self._copy)
        menu.addAction("Revelar", self._reveal)
        menu.addAction("Editar", self._edit)
        menu.addSeparator()
        menu.addAction("Excluir", self._delete)
        self._exec_menu(menu, self.table.viewport().mapToGlobal(position))
        menu.deleteLater()

    def _exec_menu(self, menu: QMenu, global_position: QPoint) -> None:
        menu.exec(global_position)

    def _add_entry(self) -> None:
        dialog = EntryDialog(self._service, self)
        if dialog.exec() == EntryDialog.DialogCode.Accepted:
            self.refresh()
            self.show_status("")
        dialog.deleteLater()

    def _edit(self) -> None:
        key = self._selected_key()
        if key is None:
            return
        try:
            dialog = EntryDialog(self._service, self, editing=key)
        except DomainError as error:
            self.show_status(str(error), error=True)
            return
        if dialog.exec() == EntryDialog.DialogCode.Accepted:
            self.refresh()
            self.show_status("Conta atualizada.")
        dialog.deleteLater()

    def _reveal(self) -> None:
        key = self._selected_key()
        if key is None:
            return
        try:
            password = self._service.get_password(*key)
        except DomainError as error:
            self.show_status(str(error), error=True)
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
            self.show_status(str(error), error=True)
            return
        self.clipboard_guard.copy_secret(password)
        seconds = CLIPBOARD_CLEAR_MS // 1000
        self.show_status(f"Senha copiada. Será apagada da área de transferência em {seconds} s.")

    def _delete(self) -> None:
        key = self._selected_key()
        if key is None or not self._confirm_delete(*key):
            return
        try:
            self._service.delete_entry(*key, confirmed=True)
        except DomainError as error:
            self.show_status(str(error), error=True)
        except OSError:
            self.show_status(DISK_ERROR_MESSAGE, error=True)
        else:
            self.refresh()
            self.show_status("Conta excluída.")

    def _confirm_delete(self, service: str, username: str | None) -> bool:
        account = service if username is None else f"{service} ({username})"
        answer = QMessageBox.question(
            self,
            "Excluir conta",
            f"Excluir a conta {account}?\nEsta ação não pode ser desfeita.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes
