import string

import pytest

from cofre.domain.models import (
    DuplicateEntryError,
    Entry,
    EntryNotFoundError,
    InvalidEntryError,
    Vault,
)
from cofre.domain.passwords import (
    MAX_GENERATED_LENGTH,
    MIN_GENERATED_LENGTH,
    SYMBOLS,
    InvalidMasterPasswordError,
    InvalidPasswordPolicyError,
    PasswordPolicy,
    generate_password,
    validate_new_master_password,
)


@pytest.mark.parametrize(
    ("service", "username", "password"),
    [("", "ana", "x"), ("   ", "ana", "x"), ("GitHub", "", "x"), ("GitHub", "ana", "")],
)
def test_entry_requires_all_fields(service, username, password):
    with pytest.raises(InvalidEntryError):
        Entry(service, username, password)


def test_entry_trims_names_but_keeps_password_intact():
    entry = Entry("  GitHub ", " ana ", "  senha  ")
    assert (entry.service, entry.username, entry.password) == ("GitHub", "ana", "  senha  ")


def test_repr_does_not_leak_password():
    entry = Entry("GitHub", "ana", "segredo-unico")
    assert "segredo-unico" not in repr(entry)
    assert "segredo-unico" not in repr(Vault((entry,)))


def test_duplicate_ignores_case_and_spaces():
    vault = Vault().added(Entry("GitHub", "ana", "a"))
    with pytest.raises(DuplicateEntryError):
        vault.added(Entry(" github ", "ANA", "b"))


def test_same_service_with_other_username_is_allowed():
    vault = Vault().added(Entry("GitHub", "ana", "a")).added(Entry("GitHub", "bia", "b"))
    assert len(vault.entries) == 2


def test_removed_returns_new_vault_and_keeps_original():
    original = Vault().added(Entry("GitHub", "ana", "a"))
    assert original.removed("github", "ANA").entries == ()
    assert len(original.entries) == 1


def test_removing_missing_entry_fails():
    with pytest.raises(EntryNotFoundError):
        Vault().removed("GitHub", "ana")


def test_sorted_entries_ignores_case():
    vault = Vault((Entry("zeta", "a", "x"), Entry("Alfa", "a", "x"), Entry("beta", "a", "x")))
    assert [entry.service for entry in vault.sorted_entries()] == ["Alfa", "beta", "zeta"]


def test_generated_password_defaults():
    password = generate_password()
    assert len(password) == 20
    assert any(char in string.ascii_lowercase for char in password)
    assert any(char in string.ascii_uppercase for char in password)
    assert any(char in string.digits for char in password)
    assert any(char in SYMBOLS for char in password)


def test_generated_passwords_differ():
    assert len({generate_password() for _ in range(100)}) == 100


def test_generator_honors_selected_classes():
    password = generate_password(PasswordPolicy(length=64, symbols=False, uppercase=False))
    assert set(password) <= set(string.ascii_lowercase + string.digits)
    assert set(password) & set(string.ascii_lowercase)
    assert set(password) & set(string.digits)


@pytest.mark.parametrize("length", [MIN_GENERATED_LENGTH, MAX_GENERATED_LENGTH])
def test_generator_accepts_length_limits(length):
    assert len(generate_password(PasswordPolicy(length=length))) == length


@pytest.mark.parametrize("length", [MIN_GENERATED_LENGTH - 1, MAX_GENERATED_LENGTH + 1])
def test_generator_rejects_length_out_of_range(length):
    with pytest.raises(InvalidPasswordPolicyError):
        PasswordPolicy(length=length)


def test_generator_requires_a_character_class():
    with pytest.raises(InvalidPasswordPolicyError):
        PasswordPolicy(lowercase=False, uppercase=False, digits=False, symbols=False)


def test_master_password_rules():
    validate_new_master_password("x" * 12, "x" * 12)
    with pytest.raises(InvalidMasterPasswordError):
        validate_new_master_password("x" * 11, "x" * 11)
    with pytest.raises(InvalidMasterPasswordError):
        validate_new_master_password("x" * 12, "y" * 12)


def test_entry_without_username_is_valid():
    entry = Entry("Wi-Fi", None, "senha-1")
    assert entry.username is None


@pytest.mark.parametrize("username", ["", "   "])
def test_blank_username_is_still_invalid(username):
    with pytest.raises(InvalidEntryError, match="usuário"):
        Entry("Wi-Fi", username, "senha-1")


def test_entry_without_username_still_requires_service_and_password():
    with pytest.raises(InvalidEntryError):
        Entry("", None, "senha-1")
    with pytest.raises(InvalidEntryError):
        Entry("Wi-Fi", None, "")


def test_only_one_entry_without_username_per_service():
    vault = Vault().added(Entry("Wi-Fi", None, "a"))
    with pytest.raises(DuplicateEntryError):
        vault.added(Entry(" wi-fi ", None, "b"))


def test_same_service_with_and_without_username_coexist():
    vault = Vault().added(Entry("Wi-Fi", None, "a")).added(Entry("Wi-Fi", "ana", "b"))
    assert len(vault.entries) == 2


def test_removed_finds_entry_without_username():
    vault = Vault().added(Entry("Wi-Fi", None, "a")).added(Entry("Wi-Fi", "ana", "b"))
    remaining = vault.removed("wi-fi", None).entries
    assert [entry.username for entry in remaining] == ["ana"]


def test_entries_without_username_sort_before_those_with_one():
    vault = Vault((Entry("Wi-Fi", "ana", "x"), Entry("Wi-Fi", None, "x")))
    assert [entry.username for entry in vault.sorted_entries()] == [None, "ana"]
