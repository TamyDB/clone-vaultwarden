"""Exportar e restaurar backups; a restauração (Argon2id) roda fora da thread da UI."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QFileDialog, QInputDialog, QLineEdit, QMessageBox, QWidget

from cofre.domain.models import DomainError
from cofre.services.vault_service import VaultService
from cofre.ui.workers import DISK_ERROR_MESSAGE, TaskRunner

FILE_FILTER = "Cofre (*.cofre);;Todos os arquivos (*)"
EXPORTED_NOTICE = "Backup exportado. Ele usa a mesma senha mestra do cofre."


class BackupActions(QObject):
    exported = Signal(str)
    restored = Signal()
    failed = Signal(str)
    busy = Signal(bool)

    def __init__(self, service: VaultService, window: QWidget) -> None:
        super().__init__(window)
        self._service = service
        self._window = window
        self._runner = TaskRunner(self)
        self._runner.succeeded.connect(self._on_restored)
        self._runner.failed.connect(self._on_restore_failed)

    def export_backup(self) -> None:
        suggested = Path.home() / f"cofre-backup-{date.today():%Y%m%d}.cofre"
        name, _filter = QFileDialog.getSaveFileName(
            self._window, "Exportar backup", str(suggested), FILE_FILTER
        )
        if not name:
            return
        try:
            self._service.export_backup(Path(name))
        except DomainError as error:
            self.failed.emit(str(error))
        except OSError:
            self.failed.emit(DISK_ERROR_MESSAGE)
        else:
            self.exported.emit(EXPORTED_NOTICE)

    def restore_backup(self) -> None:
        name, _filter = QFileDialog.getOpenFileName(
            self._window, "Restaurar backup", str(Path.home()), FILE_FILTER
        )
        if not name:
            return
        if self._service.vault_exists and not self._confirm_replace():
            return
        password, accepted = QInputDialog.getText(
            self._window,
            "Restaurar backup",
            "Senha mestra do backup:",
            QLineEdit.EchoMode.Password,
        )
        if not accepted:
            return
        source = Path(name)
        self.busy.emit(True)
        self._runner.start(lambda: self._service.restore_backup(source, password))

    def _confirm_replace(self) -> bool:
        answer = QMessageBox.question(
            self._window,
            "Restaurar backup",
            "Restaurar substitui o cofre atual.\n"
            "Uma cópia dele fica guardada no arquivo .bak, até a próxima gravação.\n\n"
            "Continuar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def _on_restored(self) -> None:
        self.busy.emit(False)
        self.restored.emit()

    def _on_restore_failed(self, message: str) -> None:
        self.busy.emit(False)
        self.failed.emit(message)
