"""Janela única do aplicativo; alterna entre o desbloqueio e o cofre aberto."""

from __future__ import annotations

from PySide6.QtWidgets import QMainWindow, QStackedWidget, QWidget

from cofre.services.vault_service import VaultService
from cofre.ui.main_view import MainView
from cofre.ui.unlock_view import UnlockView


class MainWindow(QMainWindow):
    def __init__(self, service: VaultService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._service = service
        self.setWindowTitle("Cofre")
        self.resize(480, 360)

        self.unlock_view = UnlockView(service)
        self.main_view = MainView()
        self.pages = QStackedWidget()
        self.pages.addWidget(self.unlock_view)
        self.pages.addWidget(self.main_view)
        self.setCentralWidget(self.pages)

        self.unlock_view.unlocked.connect(self._show_vault)
        self.main_view.lock_requested.connect(self._lock)

    def _show_vault(self) -> None:
        self.pages.setCurrentWidget(self.main_view)

    def _lock(self) -> None:
        self._service.lock()
        self.unlock_view.reset()
        self.pages.setCurrentWidget(self.unlock_view)
