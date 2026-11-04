import os
import socket

import pytest

from cofre.domain.models import DuplicateEntryError, EntryNotFoundError, InvalidEntryError
from cofre.domain.passwords import InvalidMasterPasswordError, generate_password
from cofre.services.vault_service import (
    ConfirmationRequiredError,
    UnlockFailedError,
    VaultAlreadyExistsError,
    VaultLockedError,
    VaultNotFoundError,
    VaultService,
)

MASTER = "senha mestra de teste"


@pytest.fixture
def path(tmp_path):
    return tmp_path / "dados" / "v.cofre"


@pytest.fixture
def service(path):
    created = VaultService(path)
    created.create(MASTER, MASTER, acknowledged_no_recovery=True)
    return created


def test_create_opens_empty_vault(service, path):
    assert path.exists()
    assert service.is_unlocked
    assert service.entries() == []


def test_create_refuses_to_overwrite_existing_vault(service, path):
    original = path.read_bytes()
    with pytest.raises(VaultAlreadyExistsError):
        VaultService(path).create(MASTER, MASTER, acknowledged_no_recovery=True)
    assert path.read_bytes() == original


def test_create_validates_master_password(path):
    with pytest.raises(InvalidMasterPasswordError):
        VaultService(path).create("curta", "curta", acknowledged_no_recovery=True)
    assert not path.exists()


def test_create_requires_no_recovery_acknowledgement(path):
    with pytest.raises(ConfirmationRequiredError):
        VaultService(path).create(MASTER, MASTER, acknowledged_no_recovery=False)
    assert not path.exists()


def test_entries_persist_after_reopening(service, path):
    service.add_entry("GitHub", "ana", "senha-1")
    service.add_entry("Banco", "ana", "senha-2")

    reopened = VaultService(path)
    assert not reopened.is_unlocked
    reopened.unlock(MASTER)

    assert [(e.service, e.username, e.password) for e in reopened.entries()] == [
        ("Banco", "ana", "senha-2"),
        ("GitHub", "ana", "senha-1"),
    ]


def test_unlock_with_wrong_password_stays_locked(service, path):
    reopened = VaultService(path)
    with pytest.raises(UnlockFailedError):
        reopened.unlock("senha errada qualquer")
    assert not reopened.is_unlocked


def test_wrong_password_and_corrupted_file_have_same_message(service, path):
    with pytest.raises(UnlockFailedError) as wrong_password:
        VaultService(path).unlock("senha errada qualquer")

    path.write_bytes(b"lixo")
    with pytest.raises(UnlockFailedError) as corrupted:
        VaultService(path).unlock(MASTER)

    assert str(wrong_password.value) == str(corrupted.value)


def test_unlock_without_vault_fails(path):
    with pytest.raises(VaultNotFoundError):
        VaultService(path).unlock(MASTER)


def test_lock_discards_key_and_data(service):
    service.add_entry("GitHub", "ana", "senha-1")
    service.lock()

    assert not service.is_unlocked
    assert service._key is None
    assert service._vault is None
    with pytest.raises(VaultLockedError):
        service.entries()
    with pytest.raises(VaultLockedError):
        service.add_entry("X", "y", "z")
    with pytest.raises(VaultLockedError):
        service.delete_entry("GitHub", "ana", confirmed=True)

    service.unlock(MASTER)
    assert len(service.entries()) == 1


def test_add_rejects_invalid_and_duplicate_entries(service):
    service.add_entry("GitHub", "ana", "senha-1")
    with pytest.raises(InvalidEntryError):
        service.add_entry("", "ana", "x")
    with pytest.raises(DuplicateEntryError):
        service.add_entry("github", "ANA", "outra")
    assert [e.password for e in service.entries()] == ["senha-1"]


def test_delete_requires_confirmation(service, path):
    service.add_entry("GitHub", "ana", "senha-1")
    before = path.read_bytes()

    with pytest.raises(ConfirmationRequiredError):
        service.delete_entry("GitHub", "ana", confirmed=False)

    assert path.read_bytes() == before
    assert len(service.entries()) == 1


def test_delete_persists(service, path):
    service.add_entry("GitHub", "ana", "senha-1")
    service.delete_entry("GitHub", "ana", confirmed=True)

    reopened = VaultService(path)
    reopened.unlock(MASTER)
    assert reopened.entries() == []


def test_delete_missing_entry_fails(service):
    with pytest.raises(EntryNotFoundError):
        service.delete_entry("GitHub", "ana", confirmed=True)


def test_memory_stays_consistent_when_disk_fails(service, path, monkeypatch):
    service.add_entry("GitHub", "ana", "senha-1")
    before = path.read_bytes()

    def fail(*_args):
        raise OSError("disco cheio")

    monkeypatch.setattr(os, "replace", fail)
    with pytest.raises(OSError, match="disco cheio"):
        service.add_entry("Banco", "ana", "senha-2")
    monkeypatch.undo()

    assert [e.service for e in service.entries()] == ["GitHub"]
    assert path.read_bytes() == before


def test_backup_file_opens_previous_state(service, path):
    service.add_entry("GitHub", "ana", "senha-1")
    service.add_entry("Banco", "ana", "senha-2")

    previous = VaultService(path.with_name(path.name + ".bak"))
    previous.unlock(MASTER)

    assert [e.service for e in previous.entries()] == ["GitHub"]


def test_full_flow_never_uses_network(path, monkeypatch):
    def blocked(*_args, **_kwargs):
        pytest.fail("O aplicativo não deve usar a rede")

    monkeypatch.setattr(socket, "socket", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(socket, "getaddrinfo", blocked)

    service = VaultService(path)
    service.create(MASTER, MASTER, acknowledged_no_recovery=True)
    service.add_entry("GitHub", "ana", generate_password())
    service.lock()
    service.unlock(MASTER)
    service.delete_entry("GitHub", "ana", confirmed=True)


def test_entry_without_username_persists_after_reopening(service, path):
    service.add_entry("Wi-Fi", None, "senha-1")
    service.add_entry("Wi-Fi", "ana", "senha-2")

    reopened = VaultService(path)
    reopened.unlock(MASTER)

    assert [(e.username, e.password) for e in reopened.entries()] == [
        (None, "senha-1"),
        ("ana", "senha-2"),
    ]


def test_delete_entry_without_username(service, path):
    service.add_entry("Wi-Fi", None, "senha-1")
    service.add_entry("Wi-Fi", "ana", "senha-2")
    service.delete_entry("Wi-Fi", None, confirmed=True)

    reopened = VaultService(path)
    reopened.unlock(MASTER)
    assert [e.username for e in reopened.entries()] == ["ana"]


def test_duplicate_entry_without_username_is_rejected(service):
    service.add_entry("Wi-Fi", None, "senha-1")
    with pytest.raises(DuplicateEntryError):
        service.add_entry("wi-fi", None, "senha-2")
