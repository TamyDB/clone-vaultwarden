import functools
import json
import os
import stat
import struct

import pytest

from cofre.crypto import vault_crypto
from cofre.domain.models import Entry, Vault
from cofre.storage import vault_file
from cofre.storage.vault_file import (
    MAX_FILE_SIZE,
    VaultAuthError,
    VaultFormatError,
    backup_path,
    decode_vault,
    encode_vault,
    new_vault_key,
    read_vault_file,
    write_vault_file,
)

MASTER = "senha mestra de teste"
HEADER_SIZE = 46


@pytest.fixture
def cached_kdf(monkeypatch):
    """Mantém rápido o teste que abre o cofre uma vez para cada byte alterado."""
    monkeypatch.setattr(vault_file, "derive_key", functools.lru_cache(vault_crypto.derive_key))


@pytest.fixture
def sample_vault():
    return Vault((Entry("ServicoSecreto", "usuario-secreto", "senha-secreta-123"),))


def test_round_trip_keeps_entries_and_key(sample_vault):
    key = new_vault_key(MASTER)
    vault, reopened_key = decode_vault(encode_vault(sample_vault, key), MASTER)
    assert vault == sample_vault
    assert reopened_key == key


def test_round_trip_with_non_ascii_text():
    vault = Vault((Entry("Ação", "joão", "pãozinho🔐"),))
    decoded, _ = decode_vault(encode_vault(vault, new_vault_key(MASTER)), MASTER)
    assert decoded == vault


def test_wrong_password_fails(sample_vault):
    blob = encode_vault(sample_vault, new_vault_key(MASTER))
    with pytest.raises(VaultAuthError):
        decode_vault(blob, "outra senha qualquer")


def test_header_size_matches_documented_layout():
    assert struct.calcsize(">4sHIII16s12s") == HEADER_SIZE


def test_no_plaintext_in_file_bytes(sample_vault, tmp_path):
    path = tmp_path / "v.cofre"
    write_vault_file(path, encode_vault(sample_vault, new_vault_key(MASTER)))
    raw = path.read_bytes()
    for secret in (b"ServicoSecreto", b"usuario-secreto", b"senha-secreta-123", b"entries"):
        assert secret not in raw


def test_nonce_changes_on_every_write_with_same_key(sample_vault):
    key = new_vault_key(MASTER)
    first, second = encode_vault(sample_vault, key), encode_vault(sample_vault, key)
    assert first[HEADER_SIZE - 12 : HEADER_SIZE] != second[HEADER_SIZE - 12 : HEADER_SIZE]
    assert first[HEADER_SIZE:] != second[HEADER_SIZE:]


def test_altering_any_byte_is_detected(sample_vault, cached_kdf):
    blob = encode_vault(sample_vault, new_vault_key(MASTER))
    for index in range(len(blob)):
        tampered = bytearray(blob)
        tampered[index] ^= 0x01
        with pytest.raises((VaultAuthError, VaultFormatError)):
            decode_vault(bytes(tampered), MASTER)


def test_every_truncation_is_detected(sample_vault, cached_kdf):
    blob = encode_vault(sample_vault, new_vault_key(MASTER))
    for size in range(len(blob)):
        with pytest.raises((VaultAuthError, VaultFormatError)):
            decode_vault(blob[:size], MASTER)


def test_bad_params_are_rejected_before_deriving_key(sample_vault, monkeypatch):
    blob = bytearray(encode_vault(sample_vault, new_vault_key(MASTER)))
    struct.pack_into(">I", blob, 6, 0xFFFFFFFF)

    def fail_if_called(*_args):
        pytest.fail("A chave não deveria ser derivada com parâmetros inválidos")

    monkeypatch.setattr(vault_file, "derive_key", fail_if_called)
    with pytest.raises(VaultFormatError):
        decode_vault(bytes(blob), MASTER)


def test_unsupported_version_is_rejected(sample_vault):
    blob = bytearray(encode_vault(sample_vault, new_vault_key(MASTER)))
    struct.pack_into(">H", blob, 4, 2)
    with pytest.raises(VaultFormatError, match="Versão"):
        decode_vault(bytes(blob), MASTER)


@pytest.mark.parametrize(
    "plaintext",
    [
        b"nao e json",
        b"[]",
        b'{"entries": 1}',
        b'{"entries": [{"service": "a"}]}',
        b'{"entries": [{"service": 1, "username": "a", "password": "b"}]}',
        json.dumps(
            {"entries": [{"service": "a", "username": "b", "password": "c"}] * 2}
        ).encode(),
    ],
)
def test_authentic_but_invalid_content_does_not_leak(plaintext, monkeypatch):
    monkeypatch.setattr(vault_file, "_serialize", lambda _vault: plaintext)
    blob = encode_vault(Vault(), new_vault_key(MASTER))
    with pytest.raises(VaultFormatError) as caught:
        decode_vault(blob, MASTER)
    assert caught.value.__cause__ is None
    assert caught.value.__suppress_context__


def test_oversized_file_is_rejected(tmp_path):
    path = tmp_path / "grande.cofre"
    with path.open("wb") as file:
        file.truncate(MAX_FILE_SIZE + 1)
    with pytest.raises(VaultFormatError):
        read_vault_file(path)


def test_write_creates_missing_directories(tmp_path):
    path = tmp_path / "a" / "b" / "v.cofre"
    write_vault_file(path, b"um")
    assert path.read_bytes() == b"um"


def test_previous_content_goes_to_backup(tmp_path):
    path = tmp_path / "v.cofre"
    write_vault_file(path, b"um")
    assert not backup_path(path).exists()
    write_vault_file(path, b"dois")
    assert path.read_bytes() == b"dois"
    assert backup_path(path).read_bytes() == b"um"


def test_failure_during_replace_preserves_vault_and_leaves_no_temp(tmp_path, monkeypatch):
    path = tmp_path / "v.cofre"
    write_vault_file(path, b"um")
    real_replace = os.replace

    def fail_on_vault(source, target):
        if os.fspath(target) == os.fspath(path):
            raise OSError("disco cheio")
        real_replace(source, target)

    monkeypatch.setattr(os, "replace", fail_on_vault)
    with pytest.raises(OSError, match="disco cheio"):
        write_vault_file(path, b"dois")

    assert path.read_bytes() == b"um"
    assert sorted(item.name for item in tmp_path.iterdir()) == ["v.cofre", "v.cofre.bak"]


def test_failure_during_write_preserves_vault(tmp_path, monkeypatch):
    path = tmp_path / "v.cofre"
    write_vault_file(path, b"um")

    def fail(_descriptor):
        raise OSError("falha de E/S")

    monkeypatch.setattr(os, "fsync", fail)
    with pytest.raises(OSError, match="falha de E/S"):
        write_vault_file(path, b"dois")

    assert path.read_bytes() == b"um"
    assert [item.name for item in tmp_path.iterdir()] == ["v.cofre"]


@pytest.mark.skipif(os.name != "posix", reason="permissões POSIX")
def test_vault_and_backup_are_private(tmp_path):
    path = tmp_path / "v.cofre"
    write_vault_file(path, b"um")
    write_vault_file(path, b"dois")
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(backup_path(path).stat().st_mode) == 0o600


def test_round_trip_keeps_entry_without_username():
    vault = Vault((Entry("Wi-Fi", None, "senha-1"), Entry("Wi-Fi", "ana", "senha-2")))
    decoded, _ = decode_vault(encode_vault(vault, new_vault_key(MASTER)), MASTER)
    assert decoded == vault
    assert {entry.username for entry in decoded.entries} == {None, "ana"}


@pytest.mark.parametrize("username", ["1", "true", '"  "', "[]"])
def test_authentic_content_with_invalid_username_does_not_leak(username, monkeypatch):
    document = {"entries": [{"service": "a", "username": json.loads(username), "password": "c"}]}
    plaintext = json.dumps(document).encode()
    monkeypatch.setattr(vault_file, "_serialize", lambda _vault: plaintext)
    blob = encode_vault(Vault(), new_vault_key(MASTER))
    with pytest.raises(VaultFormatError) as caught:
        decode_vault(blob, MASTER)
    assert caught.value.__cause__ is None
