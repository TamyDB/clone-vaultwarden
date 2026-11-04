"""Ponto de entrada: resolve caminhos, garante instância única e monta o aplicativo."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QLockFile, QStandardPaths, QThreadPool
from PySide6.QtWidgets import QApplication, QMessageBox

from cofre.selftest import SELF_TEST_FLAG, run_self_test
from cofre.services.vault_service import VaultService
from cofre.ui.main_window import MainWindow

VAULT_FILE_NAME = "vault.cofre"
LOCK_FILE_NAME = "cofre.lock"


def acquire_instance_lock(data_dir: Path) -> QLockFile | None:
    """Duas instâncias gravando o mesmo cofre perderiam dados uma da outra."""
    lock = QLockFile(str(data_dir / LOCK_FILE_NAME))
    return lock if lock.tryLock(0) else None


def main() -> int:
    if SELF_TEST_FLAG in sys.argv[1:]:
        return run_self_test()
    app = QApplication(sys.argv)
    app.setApplicationName("Cofre")

    data_dir = Path(
        QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
    )
    try:
        data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    except OSError:
        QMessageBox.critical(None, "Cofre", "Não foi possível criar a pasta de dados.")
        return 1

    lock = acquire_instance_lock(data_dir)
    if lock is None:
        QMessageBox.warning(None, "Cofre", "O Cofre já está aberto.")
        return 1

    window = MainWindow(VaultService(data_dir / VAULT_FILE_NAME))
    app.aboutToQuit.connect(window.main_view.clipboard_guard.clear_if_ours)
    window.show()
    exit_code = app.exec()
    QThreadPool.globalInstance().waitForDone()
    lock.unlock()
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
