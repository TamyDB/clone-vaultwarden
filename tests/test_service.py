import os
import socket

import pytest

from cofre.domain.models import DuplicateEntryError, EntryNotFoundError, InvalidEntryError
from cofre.domain.passwords import InvalidMasterPasswordError, generate_password
from cofre.services.vault_service import (
    BackupError,
    ConfirmationRequiredError,
    RestoreFailedError,
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


# --- Backup (F5) ---

OTHER_MASTER = "outra senha mestra!!"


@pytest.fixture
def backup_file(service, tmp_path):
    service.add_entry("GitHub", "ana", "senha-1")
    destination = tmp_path / "externo" / "copia.cofre"
    destination.parent.mkdir()
    service.export_backup(destination)
    return destination


def test_export_copies_the_encrypted_file_and_opens_with_same_password(service, path, backup_file):
    assert backup_file.read_bytes() == path.read_bytes()
    exported = VaultService(backup_file)
    exported.unlock(MASTER)
    assert [e.service for e in exported.entries()] == ["GitHub"]


def test_export_has_no_plaintext(backup_file):
    raw = backup_file.read_bytes()
    assert b"GitHub" not in raw
    assert b"senha-1" not in raw


@pytest.mark.skipif(os.name != "posix", reason="permissões POSIX")
def test_export_is_private(backup_file):
    import stat

    assert stat.S_IMODE(backup_file.stat().st_mode) == 0o600


def test_export_leaves_no_temp_files(backup_file):
    assert [item.name for item in backup_file.parent.iterdir()] == ["copia.cofre"]


def test_export_refuses_vault_and_its_backup(service, path):
    with pytest.raises(BackupError):
        service.export_backup(path)
    with pytest.raises(BackupError):
        service.export_backup(path.with_name(path.name + ".bak"))


def test_export_without_vault_fails(path, tmp_path):
    with pytest.raises(VaultNotFoundError):
        VaultService(path).export_backup(tmp_path / "x.cofre")


def test_export_works_while_locked(service, tmp_path):
    service.lock()
    service.export_backup(tmp_path / "bloqueado.cofre")
    assert (tmp_path / "bloqueado.cofre").exists()


def test_restore_replaces_vault_and_locks(service, path, backup_file):
    service.add_entry("Banco", "ana", "senha-2")
    service.restore_backup(backup_file, MASTER)

    assert not service.is_unlocked
    reopened = VaultService(path)
    reopened.unlock(MASTER)
    assert [e.service for e in reopened.entries()] == ["GitHub"]


def test_restore_keeps_previous_vault_as_bak(service, path, backup_file):
    service.add_entry("Banco", "ana", "senha-2")
    previous = path.read_bytes()
    service.restore_backup(backup_file, MASTER)
    assert path.with_name(path.name + ".bak").read_bytes() == previous


def test_restore_accepts_other_master_password(path, tmp_path):
    other_path = tmp_path / "outro.cofre"
    other = VaultService(other_path)
    other.create(OTHER_MASTER, OTHER_MASTER, acknowledged_no_recovery=True)
    other.add_entry("Serviço do backup", "bia", "senha-b")
    VaultService(path).create(MASTER, MASTER, acknowledged_no_recovery=True)

    target = VaultService(path)
    target.restore_backup(other_path, OTHER_MASTER)
    target.unlock(OTHER_MASTER)
    assert [e.service for e in target.entries()] == ["Serviço do backup"]


def test_restore_with_wrong_password_changes_nothing(service, path, backup_file):
    before = path.read_bytes()
    with pytest.raises(RestoreFailedError):
        service.restore_backup(backup_file, "senha errada qualquer")
    assert path.read_bytes() == before
    assert service.is_unlocked


def test_restore_rejects_invalid_file_with_same_message(service, path, tmp_path, backup_file):
    junk = tmp_path / "lixo.cofre"
    junk.write_bytes(b"isto nao e um cofre")
    before = path.read_bytes()

    with pytest.raises(RestoreFailedError) as invalid:
        service.restore_backup(junk, MASTER)
    with pytest.raises(RestoreFailedError) as wrong:
        service.restore_backup(backup_file, "senha errada qualquer")

    assert str(invalid.value) == str(wrong.value)
    assert path.read_bytes() == before


def test_restore_rejects_tampered_backup(service, path, backup_file):
    raw = bytearray(backup_file.read_bytes())
    raw[-1] ^= 0x01
    backup_file.write_bytes(bytes(raw))
    before = path.read_bytes()
    with pytest.raises(RestoreFailedError):
        service.restore_backup(backup_file, MASTER)
    assert path.read_bytes() == before


def test_restore_refuses_the_vault_itself(service, path):
    with pytest.raises(BackupError):
        service.restore_backup(path, MASTER)


def test_restore_from_automatic_bak_recovers_previous_state(service, path):
    service.add_entry("GitHub", "ana", "senha-1")
    service.add_entry("Banco", "ana", "senha-2")
    service.restore_backup(path.with_name(path.name + ".bak"), MASTER)

    reopened = VaultService(path)
    reopened.unlock(MASTER)
    assert [e.service for e in reopened.entries()] == ["GitHub"]


def test_restore_without_existing_vault(path, backup_file, tmp_path):
    fresh = VaultService(tmp_path / "novo" / "v.cofre")
    fresh.restore_backup(backup_file, MASTER)
    fresh.unlock(MASTER)
    assert [e.service for e in fresh.entries()] == ["GitHub"]


def test_restore_missing_source_raises_os_error(service, tmp_path):
    with pytest.raises(OSError):
        service.restore_backup(tmp_path / "nao-existe.cofre", MASTER)


def test_update_entry_persists_and_keeps_others(service, path):
    service.add_entry("GitHub", "ana", "senha-1")
    service.add_entry("Banco", "ana", "senha-2")
    service.update_entry("GitHub", "ana", "GitLab", None, "nova-senha")

    reopened = VaultService(path)
    reopened.unlock(MASTER)
    assert [(e.service, e.username, e.password) for e in reopened.entries()] == [
        ("Banco", "ana", "senha-2"),
        ("GitLab", None, "nova-senha"),
    ]


def test_update_entry_validates_and_rejects_collisions(service, path):
    service.add_entry("GitHub", "ana", "senha-1")
    service.add_entry("Banco", "ana", "senha-2")
    before = path.read_bytes()

    with pytest.raises(InvalidEntryError):
        service.update_entry("GitHub", "ana", "GitHub", "", "x")
    with pytest.raises(DuplicateEntryError):
        service.update_entry("GitHub", "ana", "banco", "ANA", "x")
    with pytest.raises(EntryNotFoundError):
        service.update_entry("Nada", "ana", "Nada", "ana", "x")
    assert path.read_bytes() == before


def test_update_entry_requires_unlocked_vault(service):
    service.add_entry("GitHub", "ana", "senha-1")
    service.lock()
    with pytest.raises(VaultLockedError):
        service.update_entry("GitHub", "ana", "GitHub", "ana", "x")


def test_update_keeps_memory_consistent_when_disk_fails(service, monkeypatch):
    service.add_entry("GitHub", "ana", "senha-1")

    def fail(*_args):
        raise OSError("disco cheio")

    monkeypatch.setattr(os, "replace", fail)
    with pytest.raises(OSError, match="disco cheio"):
        service.update_entry("GitHub", "ana", "GitHub", "ana", "nova")
    monkeypatch.undo()

    assert [e.password for e in service.entries()] == ["senha-1"]
