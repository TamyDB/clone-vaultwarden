import os
import string

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLineEdit

from cofre.services.vault_service import VaultService
from cofre.ui import main_view
from cofre.ui.entry_dialog import EntryDialog
from cofre.ui.main_view import MainView
from cofre.ui.main_window import MainWindow
from cofre.ui.workers import DISK_ERROR_MESSAGE

MASTER = "senha mestra de teste"


@pytest.fixture
def path(tmp_path):
    return tmp_path / "v.cofre"


@pytest.fixture
def service(path):
    created = VaultService(path)
    created.create(MASTER, MASTER, acknowledged_no_recovery=True)
    return created


@pytest.fixture
def dialog(qtbot, service):
    created = EntryDialog(service)
    qtbot.addWidget(created)
    return created


def fill(dialog, service="GitHub", username="ana", password="senha-1"):
    dialog.service_field.setText(service)
    dialog.username_field.setText(username)
    dialog.password_field.setText(password)


def table_rows(view):
    return [
        (view.table.item(row, 0).text(), view.table.item(row, 1).text())
        for row in range(view.table.rowCount())
    ]


def test_save_persists_and_accepts(dialog, path):
    fill(dialog)
    dialog.save_button.click()

    assert dialog.result() == EntryDialog.DialogCode.Accepted
    reopened = VaultService(path)
    reopened.unlock(MASTER)
    assert [e.password for e in reopened.entries()] == ["senha-1"]


@pytest.mark.parametrize(
    ("fields", "expected"),
    [
        ({"service": " "}, "serviço"),
        ({"username": ""}, "usuário"),
        ({"password": ""}, "senha"),
    ],
)
def test_invalid_fields_keep_typed_data(dialog, service, fields, expected):
    fill(dialog, **fields)
    typed = dialog.password_field.text()
    dialog.save_button.click()

    assert expected in dialog.message.text()
    assert dialog.result() != EntryDialog.DialogCode.Accepted
    assert dialog.password_field.text() == typed
    assert service.entries() == []


def test_duplicate_keeps_dialog_open(dialog, service):
    service.add_entry("GitHub", "ana", "original")
    fill(dialog, service="github", username="ANA", password="outra")
    dialog.save_button.click()

    assert "Já existe" in dialog.message.text()
    assert dialog.username_field.text() == "ANA"
    assert [e.password for e in service.entries()] == ["original"]


def test_disk_failure_keeps_typed_data_and_entries(dialog, service, monkeypatch):
    def fail(*_args):
        raise OSError("/caminho/secreto")

    monkeypatch.setattr(os, "replace", fail)
    fill(dialog)
    dialog.save_button.click()

    assert dialog.message.text() == DISK_ERROR_MESSAGE
    assert dialog.password_field.text() == "senha-1"
    assert service.entries() == []


def test_password_is_hidden_until_requested(dialog):
    assert dialog.password_field.echoMode() == QLineEdit.EchoMode.Password
    dialog.show_button.click()
    assert dialog.password_field.echoMode() == QLineEdit.EchoMode.Normal
    dialog.show_button.click()
    assert dialog.password_field.echoMode() == QLineEdit.EchoMode.Password


def test_generate_fills_hidden_password_with_default_length(dialog):
    dialog.generate_button.click()
    assert len(dialog.password_field.text()) == 20
    assert dialog.password_field.echoMode() == QLineEdit.EchoMode.Password


def test_generate_honors_options(dialog):
    dialog.length_field.setValue(32)
    dialog.symbols.setChecked(False)
    dialog.uppercase.setChecked(False)
    dialog.generate_button.click()

    password = dialog.password_field.text()
    assert len(password) == 32
    assert set(password) <= set(string.ascii_lowercase + string.digits)


def test_length_field_follows_limits(dialog):
    assert (dialog.length_field.minimum(), dialog.length_field.maximum()) == (12, 64)


def test_generate_without_classes_shows_message_and_keeps_password(dialog):
    dialog.password_field.setText("digitada")
    for checkbox in (dialog.lowercase, dialog.uppercase, dialog.digits, dialog.symbols):
        checkbox.setChecked(False)
    dialog.generate_button.click()

    assert "ao menos um tipo" in dialog.message.text()
    assert dialog.password_field.text() == "digitada"


def test_enter_saves_instead_of_generating(qtbot, dialog, service):
    dialog.show()
    fill(dialog)
    qtbot.keyClick(dialog.password_field, Qt.Key.Key_Return)

    assert dialog.password_field.text() == "senha-1"
    assert len(service.entries()) == 1


def test_cancel_saves_nothing(dialog, service):
    fill(dialog)
    dialog.cancel_button.click()
    assert service.entries() == []


def test_table_is_sorted_and_never_contains_password(qtbot, service):
    service.add_entry("zeta", "ana", "senha-z")
    service.add_entry("Alfa", "bia", "senha-a")
    view = MainView(service)
    qtbot.addWidget(view)
    view.refresh()

    assert table_rows(view) == [("Alfa", "bia"), ("zeta", "ana")]
    assert view.table.columnCount() == 2
    assert view.table.editTriggers() == view.table.EditTrigger.NoEditTriggers


def fake_exec(fields, click_save=True):
    def run(dialog):
        fill(dialog, **fields)
        (dialog.save_button if click_save else dialog.cancel_button).click()
        return dialog.result()

    return run


def test_add_button_updates_table_after_save(qtbot, service, monkeypatch):
    monkeypatch.setattr(main_view.EntryDialog, "exec", fake_exec({"service": "GitHub"}))
    view = MainView(service)
    qtbot.addWidget(view)
    view.add_button.click()
    assert table_rows(view) == [("GitHub", "ana")]


def test_add_button_leaves_table_after_cancel(qtbot, service, monkeypatch):
    monkeypatch.setattr(main_view.EntryDialog, "exec", fake_exec({}, click_save=False))
    view = MainView(service)
    qtbot.addWidget(view)
    view.add_button.click()
    assert table_rows(view) == []


def test_entries_survive_lock_and_table_is_cleared_while_locked(qtbot, path, service):
    window = MainWindow(VaultService(path))
    qtbot.addWidget(window)
    window.show()
    unlock = window.unlock_view

    unlock.password.setText(MASTER)
    with qtbot.waitSignal(unlock.unlocked, timeout=10000):
        unlock.submit.click()
    window._service.add_entry("GitHub", "ana", "senha-1")
    window.main_view.refresh()

    window.main_view.lock_button.click()
    assert window.main_view.table.rowCount() == 0

    unlock.password.setText(MASTER)
    with qtbot.waitSignal(unlock.unlocked, timeout=10000):
        unlock.submit.click()
    assert table_rows(window.main_view) == [("GitHub", "ana")]
