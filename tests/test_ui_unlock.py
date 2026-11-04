import os
import subprocess
import sys

import pytest
from PySide6.QtCore import Qt, QThreadPool, QTimer

from cofre.__main__ import acquire_instance_lock
from cofre.services.vault_service import VaultService
from cofre.ui.main_window import MainWindow
from cofre.ui.workers import DISK_ERROR_MESSAGE, UNEXPECTED_ERROR_MESSAGE, TaskRunner

MASTER = "senha mestra de teste"


@pytest.fixture
def path(tmp_path):
    return tmp_path / "v.cofre"


@pytest.fixture
def window(qtbot, path):
    created = MainWindow(VaultService(path))
    qtbot.addWidget(created)
    created.show()
    yield created
    QThreadPool.globalInstance().waitForDone()


@pytest.fixture
def existing_vault(path):
    VaultService(path).create(MASTER, MASTER, acknowledged_no_recovery=True)


def fill_creation(view, password=MASTER, confirmation=MASTER, acknowledged=True):
    view.password.setText(password)
    view.confirmation.setText(confirmation)
    view.acknowledgement.setChecked(acknowledged)


def submit_and_wait(qtbot, view):
    qtbot.mouseClick(view.submit, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(view.submit.isEnabled, timeout=10000)


def test_first_use_shows_creation_mode(window):
    view = window.unlock_view
    assert view.submit.text() == "Criar cofre"
    assert view.confirmation.isVisible()
    assert view.acknowledgement.isVisible()


def test_existing_vault_asks_only_for_password(existing_vault, window):
    view = window.unlock_view
    assert view.submit.text() == "Abrir"
    assert view.password.isVisible()
    assert not view.confirmation.isVisible()
    assert not view.acknowledgement.isVisible()


def test_password_fields_hide_text(window):
    assert window.unlock_view.password.echoMode() == window.unlock_view.password.EchoMode.Password
    assert (
        window.unlock_view.confirmation.echoMode()
        == window.unlock_view.confirmation.EchoMode.Password
    )


def test_create_opens_vault_and_clears_fields(qtbot, window, path):
    view = window.unlock_view
    fill_creation(view)
    with qtbot.waitSignal(view.unlocked, timeout=10000):
        qtbot.mouseClick(view.submit, Qt.MouseButton.LeftButton)

    assert window.pages.currentWidget() is window.main_view
    assert path.exists()
    assert view.password.text() == ""
    assert view.confirmation.text() == ""


@pytest.mark.parametrize(
    ("fields", "expected"),
    [
        ({"password": "curta", "confirmation": "curta"}, "ao menos 12"),
        ({"confirmation": "outra senha mestra"}, "não corresponde"),
        ({"acknowledged": False}, "não pode ser recuperada"),
    ],
)
def test_create_validations_keep_vault_uncreated(qtbot, window, path, fields, expected):
    view = window.unlock_view
    fill_creation(view, **fields)
    submit_and_wait(qtbot, view)

    assert expected in view.message.text()
    assert not path.exists()
    assert window.pages.currentWidget() is view


def test_wrong_password_shows_message_and_allows_retry(qtbot, existing_vault, window):
    view = window.unlock_view
    view.password.setText("senha errada qualquer")
    submit_and_wait(qtbot, view)

    assert view.message.text() == "Senha incorreta ou arquivo corrompido."
    assert view.password.text() == ""
    assert window.pages.currentWidget() is view

    view.password.setText(MASTER)
    with qtbot.waitSignal(view.unlocked, timeout=10000):
        qtbot.mouseClick(view.submit, Qt.MouseButton.LeftButton)
    assert window.pages.currentWidget() is window.main_view


def test_corrupted_file_shows_same_message(qtbot, existing_vault, path, window):
    path.write_bytes(b"lixo")
    view = window.unlock_view
    view.password.setText(MASTER)
    submit_and_wait(qtbot, view)
    assert view.message.text() == "Senha incorreta ou arquivo corrompido."


def test_enter_key_submits(qtbot, existing_vault, window):
    view = window.unlock_view
    view.password.setText(MASTER)
    with qtbot.waitSignal(view.unlocked, timeout=10000):
        qtbot.keyClick(view.password, Qt.Key.Key_Return)


def test_lock_returns_to_unlock_in_open_mode(qtbot, window):
    view = window.unlock_view
    fill_creation(view)
    with qtbot.waitSignal(view.unlocked, timeout=10000):
        qtbot.mouseClick(view.submit, Qt.MouseButton.LeftButton)

    qtbot.mouseClick(window.main_view.lock_button, Qt.MouseButton.LeftButton)

    assert window.pages.currentWidget() is view
    assert view.submit.text() == "Abrir"
    assert not window._service.is_unlocked


def test_window_stays_responsive_and_controls_disabled_while_deriving(
    qtbot, existing_vault, window
):
    view = window.unlock_view
    ticks = []
    timer = QTimer()
    timer.timeout.connect(lambda: ticks.append(view.submit.isEnabled()))
    timer.start(5)

    view.password.setText(MASTER)
    with qtbot.waitSignal(view.unlocked, timeout=10000):
        qtbot.mouseClick(view.submit, Qt.MouseButton.LeftButton)
    timer.stop()

    assert len(ticks) >= 3
    assert ticks[0] is False


def test_repeated_submit_while_busy_is_ignored(qtbot, existing_vault, window, monkeypatch):
    view = window.unlock_view
    started = []
    real_start = view._runner.start
    monkeypatch.setattr(
        view._runner, "start", lambda task: (started.append(task), real_start(task))
    )
    view.password.setText(MASTER)
    with qtbot.waitSignal(view.unlocked, timeout=10000):
        view.password.returnPressed.emit()
        view.password.returnPressed.emit()
    assert len(started) == 1


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (OSError("/home/ana/segredo"), DISK_ERROR_MESSAGE),
        (RuntimeError("detalhe interno"), UNEXPECTED_ERROR_MESSAGE),
    ],
)
def test_runner_hides_system_error_details(qtbot, error, expected):
    runner = TaskRunner()

    def task():
        raise error

    with qtbot.waitSignal(runner.failed, timeout=5000) as signal:
        runner.start(task)
    assert signal.args == [expected]


def test_second_instance_lock_is_refused(tmp_path):
    first = acquire_instance_lock(tmp_path)
    assert first is not None
    code = (
        "import sys\n"
        "from pathlib import Path\n"
        "from cofre.__main__ import acquire_instance_lock\n"
        "sys.exit(0 if acquire_instance_lock(Path(sys.argv[1])) is None else 1)\n"
    )
    held = subprocess.run([sys.executable, "-c", code, str(tmp_path)], check=False)  # noqa: S603
    assert held.returncode == 0

    first.unlock()
    released = subprocess.run(  # noqa: S603
        [sys.executable, "-c", code, str(tmp_path)], check=False, env=os.environ
    )
    assert released.returncode == 1
