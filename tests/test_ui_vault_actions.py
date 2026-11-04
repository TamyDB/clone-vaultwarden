import pytest
from PySide6.QtGui import QGuiApplication

from cofre.domain.models import EntryNotFoundError
from cofre.services.vault_service import VaultService
from cofre.ui import main_view
from cofre.ui.main_view import MainView
from cofre.ui.main_window import MainWindow
from cofre.ui.reveal_dialog import RevealDialog
from cofre.ui.workers import DISK_ERROR_MESSAGE

MASTER = "senha mestra de teste"
SECRET = "senha-secreta-123"


@pytest.fixture
def path(tmp_path):
    return tmp_path / "v.cofre"


@pytest.fixture
def service(path):
    created = VaultService(path)
    created.create(MASTER, MASTER, acknowledged_no_recovery=True)
    created.add_entry("GitHub", "ana", SECRET)
    created.add_entry("Wi-Fi", None, "senha-wifi")
    return created


@pytest.fixture
def view(qtbot, service):
    board = QGuiApplication.clipboard()
    board.clear()
    created = MainView(service)
    qtbot.addWidget(created)
    created.show()
    created.refresh()
    yield created
    board.clear()


def select(view, row):
    view.table.selectRow(row)


def test_action_buttons_need_a_selection(view):
    for button in (view.reveal_button, view.copy_button, view.delete_button):
        assert not button.isEnabled()
    select(view, 0)
    for button in (view.reveal_button, view.copy_button, view.delete_button):
        assert button.isEnabled()


def test_buttons_are_disabled_again_after_lock_clears_the_table(view):
    select(view, 0)
    view.clear()
    assert not view.copy_button.isEnabled()


def test_service_get_password(service):
    assert service.get_password(" github ", "ANA") == SECRET
    assert service.get_password("Wi-Fi", None) == "senha-wifi"
    with pytest.raises(EntryNotFoundError):
        service.get_password("GitHub", "outra")


def test_reveal_shows_the_password_of_the_selected_entry(view, monkeypatch):
    seen = []

    def fake_exec(dialog):
        seen.append((dialog.password_field.text(), dialog.windowTitle()))
        return 0

    monkeypatch.setattr(RevealDialog, "exec", fake_exec)
    select(view, 0)
    view.reveal_button.click()

    assert seen == [(SECRET, "Senha")]


def test_reveal_dialog_clears_field_on_close(qtbot):
    dialog = RevealDialog("GitHub", "ana", SECRET)
    qtbot.addWidget(dialog)
    assert dialog.password_field.isReadOnly()
    dialog.show()
    dialog.close_button.click()
    assert dialog.password_field.text() == ""


def test_password_never_reaches_the_table_or_status(view):
    select(view, 0)
    view.copy_button.click()
    cells = [view.table.item(r, c).text() for r in range(2) for c in range(2)]
    assert not any(SECRET in cell or "senha-wifi" in cell for cell in cells)
    assert SECRET not in view.status.text()


def test_copy_puts_password_in_clipboard_with_notice(view):
    select(view, 0)
    view.copy_button.click()
    assert QGuiApplication.clipboard().text() == SECRET
    assert "30 s" in view.status.text()


def test_copy_works_for_entry_without_username(view):
    select(view, 1)
    view.copy_button.click()
    assert QGuiApplication.clipboard().text() == "senha-wifi"


def test_lock_clears_clipboard(qtbot, path, service):
    window = MainWindow(VaultService(path))
    qtbot.addWidget(window)
    window.show()
    unlock = window.unlock_view
    unlock.password.setText(MASTER)
    with qtbot.waitSignal(unlock.unlocked, timeout=10000):
        unlock.submit.click()

    window.main_view.table.selectRow(0)
    window.main_view.copy_button.click()
    assert QGuiApplication.clipboard().text() != ""

    window.main_view.lock_button.click()
    assert QGuiApplication.clipboard().text() == ""
    assert window.main_view.status.text() == ""


def test_delete_asks_for_confirmation_with_the_entry_name(view, monkeypatch):
    asked = []
    monkeypatch.setattr(
        MainView, "_confirm_delete", lambda _self, s, u: asked.append((s, u)) or False
    )
    select(view, 0)
    view.delete_button.click()
    assert asked == [("GitHub", "ana")]


def test_declined_delete_keeps_the_entry(view, service):
    view._confirm_delete = lambda *_args: False
    select(view, 0)
    view.delete_button.click()
    assert len(service.entries()) == 2
    assert view.table.rowCount() == 2


def test_confirmed_delete_removes_and_persists(view, service, path):
    view._confirm_delete = lambda *_args: True
    select(view, 0)
    view.delete_button.click()

    assert view.table.rowCount() == 1
    assert view.status.text() == "Entrada excluída."
    reopened = VaultService(path)
    reopened.unlock(MASTER)
    assert [e.service for e in reopened.entries()] == ["Wi-Fi"]


def test_delete_entry_without_username(view, service):
    view._confirm_delete = lambda *_args: True
    select(view, 1)
    view.delete_button.click()
    assert [e.service for e in service.entries()] == ["GitHub"]


def test_delete_disk_failure_keeps_entry_and_shows_message(view, service, monkeypatch):
    import os

    def fail(*_args):
        raise OSError("/caminho/secreto")

    view._confirm_delete = lambda *_args: True
    monkeypatch.setattr(os, "replace", fail)
    select(view, 0)
    view.delete_button.click()

    assert view.status.text() == DISK_ERROR_MESSAGE
    assert len(service.entries()) == 2


def test_confirmation_default_is_no(qtbot, view, monkeypatch):
    captured = {}

    def fake_question(parent, title, text, buttons, default):
        captured.update(text=text, default=default)
        return main_view.QMessageBox.StandardButton.No

    monkeypatch.setattr(main_view.QMessageBox, "question", fake_question)
    assert view._confirm_delete("GitHub", "ana") is False
    assert "GitHub (ana)" in captured["text"]
    assert captured["default"] == main_view.QMessageBox.StandardButton.No
    assert view._confirm_delete("Wi-Fi", None) is False
