import pytest
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication, QDialog, QLineEdit

from cofre.services.vault_service import VaultService
from cofre.ui.idle_lock import IDLE_TIMEOUT_MS, IdleLock
from cofre.ui.main_window import IDLE_NOTICE, MainWindow
from cofre.ui.reveal_dialog import RevealDialog

MASTER = "senha mestra de teste"
SECRET = "senha-secreta-123"
SHORT_MS = 300


@pytest.fixture
def field(qtbot):
    widget = QLineEdit()
    qtbot.addWidget(widget)
    widget.show()
    return widget


def test_default_timeout_is_five_minutes():
    assert IDLE_TIMEOUT_MS == 5 * 60 * 1000


def test_emits_after_timeout(qtbot):
    lock = IdleLock(80)
    lock.start()
    with qtbot.waitSignal(lock.idle, timeout=3000):
        pass
    assert not lock.is_running


def test_does_nothing_until_started(qtbot):
    lock = IdleLock(60)
    with qtbot.assertNotEmitted(lock.idle, wait=250):
        pass


def test_stop_cancels_pending_timeout(qtbot):
    lock = IdleLock(80)
    lock.start()
    lock.stop()
    with qtbot.assertNotEmitted(lock.idle, wait=300):
        pass


def test_keyboard_activity_postpones_timeout(qtbot, field):
    lock = IdleLock(SHORT_MS)
    lock.start()
    with qtbot.assertNotEmitted(lock.idle):
        for _ in range(8):
            qtbot.wait(100)
            qtbot.keyClick(field, "a")
    with qtbot.waitSignal(lock.idle, timeout=3000):
        pass


def test_filter_does_not_swallow_input(qtbot, field):
    lock = IdleLock(SHORT_MS)
    lock.start()
    qtbot.keyClicks(field, "abc")
    assert field.text() == "abc"


def test_mouse_activity_postpones_timeout(qtbot, field):
    lock = IdleLock(SHORT_MS)
    lock.start()
    with qtbot.assertNotEmitted(lock.idle):
        for _ in range(8):
            qtbot.wait(100)
            qtbot.mouseMove(field)
            qtbot.mouseClick(field, Qt.MouseButton.LeftButton)


@pytest.fixture
def window(qtbot, tmp_path):
    path = tmp_path / "v.cofre"
    service = VaultService(path)
    service.create(MASTER, MASTER, acknowledged_no_recovery=True)
    service.add_entry("GitHub", "ana", SECRET)
    service.add_entry("Wi-Fi", None, "senha-wifi")
    service.lock()

    created = MainWindow(service, idle_timeout_ms=SHORT_MS)
    qtbot.addWidget(created)
    created.show()
    QGuiApplication.clipboard().clear()
    yield created
    created.idle_lock.stop()
    QGuiApplication.clipboard().clear()


def unlock(qtbot, window):
    view = window.unlock_view
    view.password.setText(MASTER)
    with qtbot.waitSignal(view.unlocked, timeout=10000):
        view.submit.click()


def wait_until_locked(qtbot, window):
    qtbot.waitUntil(lambda: window.pages.currentWidget() is window.unlock_view, timeout=5000)


def open_dialogs():
    return [w for w in QApplication.topLevelWidgets() if isinstance(w, QDialog) and w.isVisible()]


@pytest.fixture
def safety_net():
    """Se o código deixar um diálogo aberto, o teste falha em vez de ficar preso no exec()."""
    rescued = []

    def close_leftovers():
        for dialog in open_dialogs():
            rescued.append(dialog)
            dialog.reject()

    timer = QTimer(singleShot=True, interval=4000)
    timer.timeout.connect(close_leftovers)
    timer.start()
    yield rescued
    timer.stop()


def test_idle_locks_and_explains(qtbot, window):
    unlock(qtbot, window)
    assert window.idle_lock.is_running

    wait_until_locked(qtbot, window)

    assert not window._service.is_unlocked
    assert window.unlock_view.message.text() == IDLE_NOTICE
    assert window.main_view.table.rowCount() == 0
    assert window.unlock_view.password.text() == ""
    assert not window.idle_lock.is_running


def test_lock_after_idle_allows_unlocking_again(qtbot, window):
    unlock(qtbot, window)
    wait_until_locked(qtbot, window)
    unlock(qtbot, window)
    assert window.pages.currentWidget() is window.main_view
    assert window.main_view.table.rowCount() == 2


def test_manual_lock_stops_timer_and_shows_no_notice(qtbot, window):
    unlock(qtbot, window)
    window.main_view.lock_button.click()
    assert not window.idle_lock.is_running
    assert window.unlock_view.message.text() == ""


def test_activity_keeps_vault_open(qtbot, window):
    unlock(qtbot, window)
    for _ in range(8):
        qtbot.wait(100)
        qtbot.keyClick(window.main_view.table, "a")
    assert window.pages.currentWidget() is window.main_view


def test_idle_clears_clipboard(qtbot, window):
    unlock(qtbot, window)
    window.main_view.table.selectRow(0)
    window.main_view.copy_button.click()
    assert QGuiApplication.clipboard().text() == SECRET

    wait_until_locked(qtbot, window)
    assert QGuiApplication.clipboard().text() == ""


def test_idle_closes_reveal_dialog_and_wipes_password(qtbot, window, safety_net, monkeypatch):
    shown = []
    real_init = RevealDialog.__init__

    def tracking_init(self, *args, **kwargs):
        real_init(self, *args, **kwargs)
        shown.append(self)

    monkeypatch.setattr(RevealDialog, "__init__", tracking_init)
    unlock(qtbot, window)
    window.main_view.table.selectRow(0)
    QTimer.singleShot(0, window.main_view.reveal_button.click)

    wait_until_locked(qtbot, window)

    assert len(shown) == 1
    assert shown[0].password_field.text() == ""
    assert safety_net == []
    assert open_dialogs() == []


def test_idle_closes_new_entry_dialog_without_saving(qtbot, window, safety_net):
    unlock(qtbot, window)
    QTimer.singleShot(0, window.main_view.add_button.click)

    wait_until_locked(qtbot, window)

    assert safety_net == []
    assert open_dialogs() == []
    unlock(qtbot, window)
    assert window.main_view.table.rowCount() == 2


def test_idle_closes_delete_confirmation_without_deleting(qtbot, window, safety_net):
    unlock(qtbot, window)
    window.main_view.table.selectRow(0)
    QTimer.singleShot(0, window.main_view.delete_button.click)

    wait_until_locked(qtbot, window)

    assert safety_net == []
    assert open_dialogs() == []
    unlock(qtbot, window)
    assert window.main_view.table.rowCount() == 2
