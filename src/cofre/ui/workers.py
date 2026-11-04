"""Execução de operações lentas (Argon2id, disco) fora da thread da interface."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject, QThreadPool, Signal

from cofre.domain.models import DomainError

DISK_ERROR_MESSAGE = "Não foi possível acessar o arquivo do cofre. Verifique disco e permissões."
UNEXPECTED_ERROR_MESSAGE = "Não foi possível concluir a operação."


class TaskRunner(QObject):
    """Executa uma tarefa por vez; quem chama mantém a interface desativada até o sinal.

    Fica vivo junto com a tela dona, para o sinal enfileirado nunca se perder com o fim da tarefa.
    """

    succeeded = Signal()
    failed = Signal(str)

    def start(self, task: Callable[[], None]) -> None:
        QThreadPool.globalInstance().start(lambda: self._run(task))

    def _run(self, task: Callable[[], None]) -> None:
        # Só mensagens fixas ou de domínio chegam à tela: exceções de sistema trazem caminhos
        # e outros detalhes (RN8).
        try:
            task()
        except DomainError as error:
            self.failed.emit(str(error))
        except OSError:
            self.failed.emit(DISK_ERROR_MESSAGE)
        except Exception:
            self.failed.emit(UNEXPECTED_ERROR_MESSAGE)
        else:
            self.succeeded.emit()
