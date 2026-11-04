"""Primitivas criptográficas: Argon2id para derivar a chave e AES-256-GCM para cifrar."""

from __future__ import annotations

import os
import unicodedata
from dataclasses import dataclass

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id

KEY_SIZE = 32
SALT_SIZE = 16
NONCE_SIZE = 12
TAG_SIZE = 16

DEFAULT_MEMORY_KIB = 64 * 1024
DEFAULT_ITERATIONS = 3
DEFAULT_LANES = 4

# Os mínimos impedem rebaixar o custo; os máximos impedem que um arquivo adulterado esgote a
# memória, já que o cabeçalho só pode ser autenticado depois de derivar a chave.
MAX_MEMORY_KIB = 1024 * 1024
MAX_ITERATIONS = 16
MAX_LANES = 16


class DecryptionError(Exception):
    """Senha incorreta ou dados adulterados: o GCM não distingue os dois casos."""


class InvalidKdfParamsError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class KdfParams:
    memory_kib: int = DEFAULT_MEMORY_KIB
    iterations: int = DEFAULT_ITERATIONS
    lanes: int = DEFAULT_LANES

    def __post_init__(self) -> None:
        if (
            not DEFAULT_MEMORY_KIB <= self.memory_kib <= MAX_MEMORY_KIB
            or not DEFAULT_ITERATIONS <= self.iterations <= MAX_ITERATIONS
            or not 1 <= self.lanes <= MAX_LANES
        ):
            raise InvalidKdfParamsError("Parâmetros de derivação fora dos limites aceitos.")


def new_salt() -> bytes:
    return os.urandom(SALT_SIZE)


def new_nonce() -> bytes:
    return os.urandom(NONCE_SIZE)


def derive_key(master_password: str, salt: bytes, params: KdfParams) -> bytes:
    # NFKC: o mesmo texto pode chegar em bytes diferentes no Windows e no Linux ("é" composto
    # ou decomposto), e o cofre precisa abrir nos dois.
    normalized = unicodedata.normalize("NFKC", master_password)
    kdf = Argon2id(
        salt=salt,
        length=KEY_SIZE,
        iterations=params.iterations,
        lanes=params.lanes,
        memory_cost=params.memory_kib,
    )
    return kdf.derive(normalized.encode("utf-8"))


def seal(key: bytes, nonce: bytes, plaintext: bytes, aad: bytes) -> bytes:
    return AESGCM(key).encrypt(nonce, plaintext, aad)


def unseal(key: bytes, nonce: bytes, ciphertext: bytes, aad: bytes) -> bytes:
    try:
        return AESGCM(key).decrypt(nonce, ciphertext, aad)
    except InvalidTag as error:
        raise DecryptionError from error
