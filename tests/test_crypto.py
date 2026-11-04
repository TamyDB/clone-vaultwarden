import unicodedata

import pytest

from cofre.crypto import vault_crypto
from cofre.crypto.vault_crypto import (
    DecryptionError,
    InvalidKdfParamsError,
    KdfParams,
    derive_key,
    new_nonce,
    new_salt,
    seal,
    unseal,
)


def test_seal_round_trip():
    key = derive_key("senha mestra longa", new_salt(), KdfParams())
    nonce = new_nonce()
    assert unseal(key, nonce, seal(key, nonce, b"dados", b"aad"), b"aad") == b"dados"


def test_derivation_depends_on_password_and_salt():
    salt = new_salt()
    params = KdfParams()
    key = derive_key("senha mestra longa", salt, params)
    assert len(key) == 32
    assert key == derive_key("senha mestra longa", salt, params)
    assert key != derive_key("outra senha longa!", salt, params)
    assert key != derive_key("senha mestra longa", new_salt(), params)


def test_equivalent_unicode_forms_derive_same_key():
    salt = new_salt()
    composed = unicodedata.normalize("NFC", "coração seguro")
    decomposed = unicodedata.normalize("NFD", "coração seguro")
    assert composed != decomposed
    assert derive_key(composed, salt, KdfParams()) == derive_key(decomposed, salt, KdfParams())


@pytest.mark.parametrize("wrong", ["key", "nonce", "ciphertext", "aad"])
def test_unseal_rejects_any_wrong_input(wrong):
    key, nonce = bytes(32), bytes(12)
    args = {"key": key, "nonce": nonce, "ciphertext": seal(key, nonce, b"dados", b"aad"),
            "aad": b"aad"}
    args[wrong] = bytes([args[wrong][0] ^ 1]) + args[wrong][1:]
    with pytest.raises(DecryptionError):
        unseal(**args)


@pytest.mark.parametrize(
    "params",
    [
        {"memory_kib": 1024},
        {"memory_kib": 1024 * 1024 + 1},
        {"iterations": 2},
        {"iterations": 17},
        {"lanes": 0},
        {"lanes": 17},
    ],
)
def test_out_of_range_params_are_rejected(params):
    with pytest.raises(InvalidKdfParamsError):
        KdfParams(**params)


def test_defaults_follow_the_documented_profile():
    assert KdfParams() == KdfParams(memory_kib=65536, iterations=3, lanes=4)
    assert vault_crypto.KEY_SIZE == 32
