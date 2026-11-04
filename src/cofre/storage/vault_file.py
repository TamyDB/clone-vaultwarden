"""Formato binário do cofre e gravação segura em disco.

Layout (big-endian), com o cabeçalho inteiro autenticado como AAD:

    magic "COFR" | versão u16 | memória u32 | iterações u32 | pistas u32
    | salt 16 bytes | nonce 12 bytes | ciphertext + tag
"""

from __future__ import annotations

import json
import os
import struct
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from cofre.crypto.vault_crypto import (
    TAG_SIZE,
    DecryptionError,
    InvalidKdfParamsError,
    KdfParams,
    derive_key,
    new_nonce,
    new_salt,
    seal,
    unseal,
)
from cofre.domain.models import DomainError, Entry, Vault

MAGIC = b"COFR"
FORMAT_VERSION = 1
BACKUP_SUFFIX = ".bak"
MAX_FILE_SIZE = 64 * 1024 * 1024

_HEADER = struct.Struct(">4sHIII16s12s")


class VaultFormatError(Exception):
    """O arquivo não é um cofre válido nesta versão do aplicativo."""


class VaultAuthError(Exception):
    """Senha incorreta ou arquivo adulterado."""


@dataclass(frozen=True, slots=True)
class VaultKey:
    """Chave derivada, mantida em memória enquanto o cofre está aberto."""

    key: bytes = field(repr=False)
    salt: bytes
    params: KdfParams


def new_vault_key(master_password: str) -> VaultKey:
    salt = new_salt()
    params = KdfParams()
    return VaultKey(derive_key(master_password, salt, params), salt, params)


def encode_vault(vault: Vault, vault_key: VaultKey) -> bytes:
    nonce = new_nonce()
    params = vault_key.params
    header = _HEADER.pack(
        MAGIC,
        FORMAT_VERSION,
        params.memory_kib,
        params.iterations,
        params.lanes,
        vault_key.salt,
        nonce,
    )
    return header + seal(vault_key.key, nonce, _serialize(vault), header)


def decode_vault(blob: bytes, master_password: str) -> tuple[Vault, VaultKey]:
    if len(blob) < _HEADER.size + TAG_SIZE:
        raise VaultFormatError("Arquivo truncado.")
    header = blob[: _HEADER.size]
    magic, version, memory_kib, iterations, lanes, salt, nonce = _HEADER.unpack(header)
    if magic != MAGIC:
        raise VaultFormatError("O arquivo não é um cofre.")
    if version != FORMAT_VERSION:
        raise VaultFormatError("Versão de cofre não suportada.")
    try:
        params = KdfParams(memory_kib, iterations, lanes)
    except InvalidKdfParamsError as error:
        raise VaultFormatError("Parâmetros de derivação inválidos.") from error

    key = derive_key(master_password, salt, params)
    try:
        plaintext = unseal(key, nonce, blob[_HEADER.size :], header)
    except DecryptionError as error:
        raise VaultAuthError from error
    return _deserialize(plaintext), VaultKey(key, salt, params)


def read_vault_file(path: Path) -> bytes:
    with path.open("rb") as file:
        blob = file.read(MAX_FILE_SIZE + 1)
    if len(blob) > MAX_FILE_SIZE:
        raise VaultFormatError("Arquivo grande demais para ser um cofre.")
    return blob


def write_vault_file(path: Path, blob: bytes) -> None:
    """Preserva o conteúdo anterior em `.bak` e só então substitui o cofre, de forma atômica."""
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.exists():
        _write_atomic(backup_path(path), path.read_bytes())
    _write_atomic(path, blob)


def backup_path(path: Path) -> Path:
    return path.with_name(path.name + BACKUP_SUFFIX)


def _write_atomic(path: Path, data: bytes) -> None:
    # mkstemp cria o arquivo com permissão 0600 no Linux, e os.replace a preserva.
    descriptor, temp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(descriptor, "wb") as file:
            file.write(data)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temp_name, path)
    except BaseException:
        Path(temp_name).unlink(missing_ok=True)
        raise
    _sync_directory(path.parent)


def _sync_directory(directory: Path) -> None:
    # Sem isso, uma queda de energia pode desfazer a troca de nomes. O Windows não permite
    # abrir diretórios desta forma.
    if os.name != "posix":
        return
    descriptor = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _serialize(vault: Vault) -> bytes:
    entries = [
        {"service": entry.service, "username": entry.username, "password": entry.password}
        for entry in vault.entries
    ]
    return json.dumps({"entries": entries}, ensure_ascii=False).encode("utf-8")


def _deserialize(plaintext: bytes) -> Vault:
    try:
        document = json.loads(plaintext)
        return Vault(
            tuple(
                Entry(item["service"], item["username"], item["password"])
                for item in document["entries"]
            )
        )
    except (ValueError, KeyError, TypeError, AttributeError, DomainError):
        # `from None`: a exceção original poderia carregar trechos do conteúdo decifrado (RN8).
        raise VaultFormatError("Conteúdo do cofre inválido.") from None
