"""Janela única do aplicativo; alterna entre o desbloqueio e o cofre aberto."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication, QDialog, QMainWindow, QStackedWidget, QWidget

from cofre.services.vault_service import VaultService
from cofre.ui.backup_actions import BackupActions
from cofre.ui.idle_lock import IDLE_TIMEOUT_MS, IdleLock
from cofre.ui.main_view import MainView
from cofre.ui.unlock_view import UnlockView

IDLE_NOTICE = "Cofre bloqueado por inatividade."
RESTORED_NOTICE = "Backup restaurado. Abra o cofre com a senha mestra do backup."


class MainWindow(QMainWindow):
    def __init__(
        self,
        service: VaultService,
        idle_timeout_ms: int = IDLE_TIMEOUT_MS,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._service = service
        self.setWindowTitle("Cofre")
        self.setMinimumSize(660, 480)
        self.resize(780, 560)

        self.unlock_view = UnlockView(service)
        self.main_view = MainView(service)
        self.idle_lock = IdleLock(idle_timeout_ms, self)
        self.backup = BackupActions(service, self)
        self.pages = QStackedWidget()
        self.pages.addWidget(self.unlock_view)
        self.pages.addWidget(self.main_view)
        self.setCentralWidget(self.pages)

        self.unlock_view.unlocked.connect(self._show_vault)
        self.main_view.lock_requested.connect(self._lock)
        self.idle_lock.idle.connect(self._lock_for_inactivity)
        self.main_view.export_requested.connect(self.backup.export_backup)
        self.main_view.restore_requested.connect(self.backup.restore_backup)
        self.unlock_view.restore_requested.connect(self.backup.restore_backup)
        self.backup.exported.connect(self._show_message)
        self.backup.failed.connect(self._show_error)
        self.backup.busy.connect(self._set_busy)
        self.backup.restored.connect(lambda: self._lock(RESTORED_NOTICE))

    def _show_vault(self) -> None:
        self.main_view.refresh()
        self.pages.setCurrentWidget(self.main_view)
        self.main_view.focus_list()
        self.idle_lock.start()

    def _lock(self, notice: str = "") -> None:
        self.idle_lock.stop()
        self.main_view.clear()
        self._service.lock()
        self.unlock_view.reset(notice)
        self.pages.setCurrentWidget(self.unlock_view)

    def _lock_for_inactivity(self) -> None:
        # Diálogos e menus abertos (revelar senha, nova conta, confirmações) são fechados antes:
        # um deles poderia estar mostrando uma senha na tela.
        popup = QApplication.activePopupWidget()
        if popup is not None:
            popup.close()
        for widget in QApplication.topLevelWidgets():
            if isinstance(widget, QDialog) and widget.isVisible():
                widget.reject()
        self._lock(IDLE_NOTICE)

    def _show_message(self, message: str, *, error: bool = False) -> None:
        if self.pages.currentWidget() is self.main_view:
            self.main_view.show_status(message, error=error)
        else:
            self.unlock_view.show_message(message, error=error)

    def _show_error(self, message: str) -> None:
        self._show_message(message, error=True)

    def _set_busy(self, busy: bool) -> None:
        # A restauração roda em segundo plano e mexe no cofre: nada mais pode agir nesse intervalo,
        # nem o bloqueio por inatividade.
        self.pages.setEnabled(not busy)
        if busy:
            self.idle_lock.stop()
        elif self.pages.currentWidget() is self.main_view:
            self.idle_lock.start()
