"""Área de transferência para segredos (RN5): marca o conteúdo como sensível e o apaga depois."""

from __future__ import annotations

import hashlib
import sys

from PySide6.QtCore import QMimeData, QObject, QTimer
from PySide6.QtGui import QClipboard

CLIPBOARD_CLEAR_MS = 30_000

# Pedem a gerenciadores de área de transferência que não guardem nem sincronizem o conteúdo.
# Só os que respeitam essa convenção obedecem; ver docs/ARQUITETURA.md.
if sys.platform == "win32":
    SENSITIVE_HINTS = {
        "ExcludeClipboardContentFromMonitorProcessing": b"\x01\x00\x00\x00",
        "CanIncludeInClipboardHistory": b"\x00\x00\x00\x00",
        "CanUploadToCloudClipboard": b"\x00\x00\x00\x00",
    }
else:
    SENSITIVE_HINTS = {"x-kde-passwordManagerHint": b"secret"}


def _digest(text: str) -> bytes:
    return hashlib.sha256(text.encode("utf-8")).digest()


class ClipboardGuard(QObject):
    def __init__(
        self,
        clipboard: QClipboard,
        timeout_ms: int = CLIPBOARD_CLEAR_MS,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._clipboard = clipboard
        # Guarda só o resumo, para não manter mais uma cópia da senha em memória.
        self._copied_digest: bytes | None = None
        self._timer = QTimer(self, singleShot=True, interval=timeout_ms)
        self._timer.timeout.connect(self.clear_if_ours)

    def copy_secret(self, text: str) -> None:
        mime = QMimeData()
        mime.setText(text)
        for mime_format, value in SENSITIVE_HINTS.items():
            mime.setData(mime_format, value)
        self._clipboard.setMimeData(mime)
        self._copied_digest = _digest(text)
        self._timer.start()

    def clear_if_ours(self) -> None:
        """Só apaga se o conteúdo ainda for o copiado: não destrói o que o usuário copiou depois."""
        self._timer.stop()
        digest, self._copied_digest = self._copied_digest, None
        if digest is not None and _digest(self._clipboard.text()) == digest:
            self._clipboard.clear()
