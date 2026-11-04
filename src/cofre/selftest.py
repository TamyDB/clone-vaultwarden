"""Autoteste sem interface: confirma que as partes nativas (criptografia, Qt) funcionam no pacote.

Usado pelo CI e por quem recebe o executável: `cofre --self-test` termina com código 0 se tudo
funcionar. Trabalha só em uma pasta temporária e não toca no cofre do usuário.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from cofre.domain.passwords import generate_password
from cofre.services.vault_service import VaultService

SELF_TEST_FLAG = "--self-test"
_MASTER = "autoteste-senha-mestra"


def run_self_test() -> int:
    try:
        # Importa o que a interface usa: falha aqui indica Qt ausente no pacote.
        from PySide6.QtCore import QCoreApplication  # noqa: F401
        from PySide6.QtWidgets import QApplication  # noqa: F401

        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "selftest.cofre"
            service = VaultService(path)
            service.create(_MASTER, _MASTER, acknowledged_no_recovery=True)
            password = generate_password()
            service.add_entry("Autoteste", None, password)
            service.lock()
            service.unlock(_MASTER)
            if service.get_password("Autoteste", None) != password:
                return 1
            if password.encode() in path.read_bytes():
                return 1
    except Exception:
        return 1
    return 0
