import pytest
from PySide6.QtWidgets import QInputDialog

from cofre.services.vault_service import VaultService
from cofre.ui import backup_actions
from cofre.ui.backup_actions import EXPORTED_NOTICE, BackupActions
from cofre.ui.main_window import RESTORED_NOTICE, MainWindow
from cofre.ui.workers import DISK_ERROR_MESSAGE

MASTER = "senha mestra de teste"
OTHER_MASTER = "outra senha mestra!!"


@pytest.fixture
def path(tmp_path):
    return tmp_path / "v.cofre"


@pytest.fixture
def window(qtbot, path):
    service = VaultService(path)
    service.create(MASTER, MASTER, acknowledged_no_recovery=True)
    service.add_entry("GitHub", "ana", "senha-1")
    service.lock()
    created = MainWindow(service)
    qtbot.addWidget(created)
    created.show()
    yield created
    created.idle_lock.stop()


def unlock(qtbot, window, password=MASTER):
    window.unlock_view.password.setText(password)
    with qtbot.waitSignal(window.unlock_view.unlocked, timeout=10000):
        window.unlock_view.submit.click()


def pick_files(monkeypatch, *, save=None, open_=None):
    monkeypatch.setattr(
        backup_actions.QFileDialog, "getSaveFileName", lambda *_a, **_k: (str(save or ""), "")
    )
    monkeypatch.setattr(
        backup_actions.QFileDialog, "getOpenFileName", lambda *_a, **_k: (str(open_ or ""), "")
    )


def answer_password(monkeypatch, password, accepted=True):
    monkeypatch.setattr(QInputDialog, "getText", lambda *_a, **_k: (password, accepted))


def make_other_backup(tmp_path):
    other_path = tmp_path / "outro" / "backup.cofre"
    other = VaultService(other_path)
    other.create(OTHER_MASTER, OTHER_MASTER, acknowledged_no_recovery=True)
    other.add_entry("Do backup", "bia", "senha-b")
    return other_path


def wait_restored(qtbot, window):
    qtbot.waitUntil(lambda: window.pages.isEnabled(), timeout=10000)


def test_export_writes_file_and_shows_notice(qtbot, window, tmp_path, monkeypatch):
    unlock(qtbot, window)
    destination = tmp_path / "copia.cofre"
    pick_files(monkeypatch, save=destination)

    window.main_view.export_button.click()

    assert destination.exists()
    assert window.main_view.status.text() == EXPORTED_NOTICE


def test_export_cancelled_does_nothing(qtbot, window, tmp_path, monkeypatch):
    unlock(qtbot, window)
    pick_files(monkeypatch, save="")
    window.main_view.export_button.click()
    assert window.main_view.status.text() == ""
    assert sorted(item.name for item in tmp_path.iterdir()) == ["v.cofre", "v.cofre.bak"]


def test_export_over_the_vault_is_refused(qtbot, window, path, monkeypatch):
    unlock(qtbot, window)
    before = path.read_bytes()
    pick_files(monkeypatch, save=path)

    window.main_view.export_button.click()

    assert "local diferente" in window.main_view.status.text()
    assert path.read_bytes() == before


def test_export_disk_failure_shows_generic_message(qtbot, window, tmp_path, monkeypatch):
    unlock(qtbot, window)
    pick_files(monkeypatch, save=tmp_path / "nao-existe" / "copia.cofre")
    window.main_view.export_button.click()
    assert window.main_view.status.text() == DISK_ERROR_MESSAGE


def test_restore_from_main_view_replaces_vault_and_locks(qtbot, window, tmp_path, monkeypatch):
    unlock(qtbot, window)
    other = make_other_backup(tmp_path)
    pick_files(monkeypatch, open_=other)
    answer_password(monkeypatch, OTHER_MASTER)
    monkeypatch.setattr(BackupActions, "_confirm_replace", lambda _self: True)

    window.main_view.restore_button.click()
    qtbot.waitUntil(lambda: window.pages.currentWidget() is window.unlock_view, timeout=10000)
    wait_restored(qtbot, window)

    assert window.unlock_view.message.text() == RESTORED_NOTICE
    assert not window._service.is_unlocked
    assert not window.idle_lock.is_running
    unlock(qtbot, window, OTHER_MASTER)
    assert [e.service for e in window._service.entries()] == ["Do backup"]


def test_restore_asks_confirmation_and_declining_changes_nothing(
    qtbot, window, path, tmp_path, monkeypatch
):
    unlock(qtbot, window)
    before = path.read_bytes()
    pick_files(monkeypatch, open_=make_other_backup(tmp_path))
    asked = []
    monkeypatch.setattr(
        QInputDialog, "getText", lambda *_a, **_k: asked.append("senha") or (OTHER_MASTER, True)
    )
    monkeypatch.setattr(BackupActions, "_confirm_replace", lambda _self: False)

    window.main_view.restore_button.click()

    assert asked == []
    assert path.read_bytes() == before
    assert window.pages.currentWidget() is window.main_view


def test_confirmation_defaults_to_no(window, monkeypatch):
    captured = {}

    def fake_question(parent, title, text, buttons, default):
        captured["default"] = default
        return backup_actions.QMessageBox.StandardButton.No

    monkeypatch.setattr(backup_actions.QMessageBox, "question", fake_question)
    assert window.backup._confirm_replace() is False
    assert captured["default"] == backup_actions.QMessageBox.StandardButton.No


def test_restore_wrong_password_keeps_vault_open_and_reports(
    qtbot, window, path, tmp_path, monkeypatch
):
    unlock(qtbot, window)
    before = path.read_bytes()
    pick_files(monkeypatch, open_=make_other_backup(tmp_path))
    answer_password(monkeypatch, "senha errada qualquer")
    monkeypatch.setattr(BackupActions, "_confirm_replace", lambda _self: True)

    window.main_view.restore_button.click()
    qtbot.waitUntil(
        lambda: window.main_view.status.text() == "Senha incorreta ou backup inválido.",
        timeout=10000,
    )
    wait_restored(qtbot, window)

    assert path.read_bytes() == before
    assert window.pages.currentWidget() is window.main_view
    assert window._service.is_unlocked
    assert window.idle_lock.is_running


def test_restore_cancelled_at_password_prompt_changes_nothing(
    qtbot, window, path, tmp_path, monkeypatch
):
    unlock(qtbot, window)
    before = path.read_bytes()
    pick_files(monkeypatch, open_=make_other_backup(tmp_path))
    answer_password(monkeypatch, OTHER_MASTER, accepted=False)
    monkeypatch.setattr(BackupActions, "_confirm_replace", lambda _self: True)

    window.main_view.restore_button.click()

    assert path.read_bytes() == before
    assert window.pages.isEnabled()


def test_restore_from_unlock_screen_without_a_vault(qtbot, tmp_path, monkeypatch):
    other = make_other_backup(tmp_path)
    fresh_path = tmp_path / "novo" / "v.cofre"
    window = MainWindow(VaultService(fresh_path))
    qtbot.addWidget(window)
    window.show()
    assert window.unlock_view.submit.text() == "Criar cofre"
    pick_files(monkeypatch, open_=other)
    answer_password(monkeypatch, OTHER_MASTER)

    window.unlock_view.restore_button.click()
    qtbot.waitUntil(lambda: window.unlock_view.submit.text() == "Abrir", timeout=10000)
    wait_restored(qtbot, window)

    assert window.unlock_view.message.text() == RESTORED_NOTICE
    assert fresh_path.exists()
    unlock(qtbot, window, OTHER_MASTER)
    assert [e.service for e in window._service.entries()] == ["Do backup"]


def test_restore_recovers_corrupted_vault_from_automatic_bak(qtbot, window, path, monkeypatch):
    unlock(qtbot, window)
    window._service.add_entry("Banco", "ana", "senha-2")
    window.main_view.lock_button.click()
    path.write_bytes(b"cofre corrompido")
    pick_files(monkeypatch, open_=path.with_name(path.name + ".bak"))
    answer_password(monkeypatch, MASTER)
    monkeypatch.setattr(BackupActions, "_confirm_replace", lambda _self: True)

    window.unlock_view.restore_button.click()
    qtbot.waitUntil(lambda: window.unlock_view.message.text() == RESTORED_NOTICE, timeout=10000)
    wait_restored(qtbot, window)

    unlock(qtbot, window)
    assert [e.service for e in window._service.entries()] == ["GitHub"]


def test_window_is_disabled_while_restoring(qtbot, window, tmp_path, monkeypatch):
    unlock(qtbot, window)
    pick_files(monkeypatch, open_=make_other_backup(tmp_path))
    answer_password(monkeypatch, OTHER_MASTER)
    monkeypatch.setattr(BackupActions, "_confirm_replace", lambda _self: True)
    states = []
    window.backup.busy.connect(
        lambda busy: states.append((busy, window.pages.isEnabled(), window.idle_lock.is_running))
    )

    window.main_view.restore_button.click()
    wait_restored(qtbot, window)
    qtbot.waitUntil(lambda: len(states) == 2, timeout=10000)

    assert states[0] == (True, False, False)
    assert states[1][:2] == (False, True)
