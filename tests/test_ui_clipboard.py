import sys

import pytest
from PySide6.QtGui import QGuiApplication

from cofre.ui import clipboard
from cofre.ui.clipboard import SENSITIVE_HINTS, ClipboardGuard

SECRET = "senha-secreta-123"


@pytest.fixture
def system_clipboard(qapp):
    board = QGuiApplication.clipboard()
    board.clear()
    yield board
    board.clear()


@pytest.fixture
def guard(system_clipboard):
    return ClipboardGuard(system_clipboard, timeout_ms=60)


def test_copy_puts_secret_in_clipboard(guard, system_clipboard):
    guard.copy_secret(SECRET)
    assert system_clipboard.text() == SECRET


def test_copy_marks_content_as_sensitive(guard, system_clipboard):
    guard.copy_secret(SECRET)
    mime = system_clipboard.mimeData()
    assert SENSITIVE_HINTS
    for mime_format, value in SENSITIVE_HINTS.items():
        assert mime.hasFormat(mime_format)
        assert bytes(mime.data(mime_format)) == value


def test_hints_match_platform():
    expected = "ExcludeClipboardContentFromMonitorProcessing" if sys.platform == "win32" else (
        "x-kde-passwordManagerHint"
    )
    assert expected in clipboard.SENSITIVE_HINTS


def test_clipboard_is_cleared_after_timeout(qtbot, guard, system_clipboard):
    guard.copy_secret(SECRET)
    qtbot.waitUntil(lambda: system_clipboard.text() == "", timeout=3000)


def test_newer_clipboard_content_is_not_cleared(qtbot, guard, system_clipboard):
    guard.copy_secret(SECRET)
    system_clipboard.setText("outra coisa copiada depois")
    qtbot.wait(250)
    assert system_clipboard.text() == "outra coisa copiada depois"


def test_clear_if_ours_clears_immediately_and_only_once(guard, system_clipboard):
    guard.copy_secret(SECRET)
    guard.clear_if_ours()
    assert system_clipboard.text() == ""

    system_clipboard.setText(SECRET)
    guard.clear_if_ours()
    assert system_clipboard.text() == SECRET


def test_clear_without_copy_leaves_clipboard_alone(guard, system_clipboard):
    system_clipboard.setText("do usuário")
    guard.clear_if_ours()
    assert system_clipboard.text() == "do usuário"


def test_second_copy_replaces_first(guard, system_clipboard):
    guard.copy_secret("primeira-senha")
    guard.copy_secret(SECRET)
    guard.clear_if_ours()
    assert system_clipboard.text() == ""


def test_guard_does_not_keep_plaintext(guard):
    guard.copy_secret(SECRET)
    assert SECRET not in repr(vars(guard))
    assert SECRET.encode() not in b"".join(
        value for value in vars(guard).values() if isinstance(value, bytes)
    )
