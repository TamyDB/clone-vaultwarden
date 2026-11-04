"""Janela única do aplicativo; alterna entre o desbloqueio e o cofre aberto."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication, QDialog, QMainWindow, QStackedWidget, QWidget

from cofre.services.vault_service import VaultService
from cofre.ui.idle_lock import IDLE_TIMEOUT_MS, IdleLock
from cofre.ui.main_view import MainView
from cofre.ui.unlock_view import UnlockView

IDLE_NOTICE = "Cofre bloqueado por inatividade."


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
        self.resize(480, 360)

        self.unlock_view = UnlockView(service)
        self.main_view = MainView(service)
        self.idle_lock = IdleLock(idle_timeout_ms, self)
        self.pages = QStackedWidget()
        self.pages.addWidget(self.unlock_view)
        self.pages.addWidget(self.main_view)
        self.setCentralWidget(self.pages)

        self.unlock_view.unlocked.connect(self._show_vault)
        self.main_view.lock_requested.connect(self._lock)
        self.idle_lock.idle.connect(self._lock_for_inactivity)

    def _show_vault(self) -> None:
        self.main_view.refresh()
        self.pages.setCurrentWidget(self.main_view)
        self.idle_lock.start()

    def _lock(self, notice: str = "") -> None:
        self.idle_lock.stop()
        self.main_view.clear()
        self._service.lock()
        self.unlock_view.reset(notice)
        self.pages.setCurrentWidget(self.unlock_view)

    def _lock_for_inactivity(self) -> None:
        # Diálogos abertos (revelar senha, nova entrada, confirmações) são fechados antes:
        # um deles poderia estar mostrando uma senha na tela.
        for widget in QApplication.topLevelWidgets():
            if isinstance(widget, QDialog) and widget.isVisible():
                widget.reject()
        self._lock(IDLE_NOTICE)
