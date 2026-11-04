"""Detecta inatividade do usuário no aplicativo inteiro (RN6)."""

from __future__ import annotations

from PySide6.QtCore import QCoreApplication, QEvent, QObject, QTimer, Signal

IDLE_TIMEOUT_MS = 5 * 60 * 1000

INPUT_EVENTS = frozenset(
    {
        QEvent.Type.MouseButtonPress,
        QEvent.Type.MouseButtonRelease,
        QEvent.Type.MouseMove,
        QEvent.Type.Wheel,
        QEvent.Type.KeyPress,
        QEvent.Type.KeyRelease,
        QEvent.Type.TouchBegin,
        QEvent.Type.TouchUpdate,
    }
)


class IdleLock(QObject):
    idle = Signal()

    def __init__(self, timeout_ms: int = IDLE_TIMEOUT_MS, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._timer = QTimer(self, singleShot=True, interval=timeout_ms)
        self._timer.timeout.connect(self.idle)
        QCoreApplication.instance().installEventFilter(self)

    @property
    def is_running(self) -> bool:
        return self._timer.isActive()

    def start(self) -> None:
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        # Só reinicia a contagem enquanto está ativo, e nunca consome o evento.
        if self._timer.isActive() and event.type() in INPUT_EVENTS:
            self._timer.start()
        return False
