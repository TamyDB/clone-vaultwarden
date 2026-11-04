"""Gerador de senhas (RN3) e validação da senha mestra (RN2)."""

from __future__ import annotations

import secrets
import string
from dataclasses import dataclass

from cofre.domain.models import DomainError

MIN_MASTER_PASSWORD_LENGTH = 12
MIN_GENERATED_LENGTH = 12
MAX_GENERATED_LENGTH = 64
DEFAULT_GENERATED_LENGTH = 20
SYMBOLS = "!@#$%&*()-_=+[]{};:,.?/"


class InvalidMasterPasswordError(DomainError):
    pass


class InvalidPasswordPolicyError(DomainError):
    pass


@dataclass(frozen=True, slots=True)
class PasswordPolicy:
    length: int = DEFAULT_GENERATED_LENGTH
    lowercase: bool = True
    uppercase: bool = True
    digits: bool = True
    symbols: bool = True

    def __post_init__(self) -> None:
        if not MIN_GENERATED_LENGTH <= self.length <= MAX_GENERATED_LENGTH:
            raise InvalidPasswordPolicyError(
                f"O tamanho deve estar entre {MIN_GENERATED_LENGTH} e {MAX_GENERATED_LENGTH}."
            )
        if not self.character_classes():
            raise InvalidPasswordPolicyError("Selecione ao menos um tipo de caractere.")

    def character_classes(self) -> list[str]:
        candidates = (
            (self.lowercase, string.ascii_lowercase),
            (self.uppercase, string.ascii_uppercase),
            (self.digits, string.digits),
            (self.symbols, SYMBOLS),
        )
        return [characters for enabled, characters in candidates if enabled]


def generate_password(policy: PasswordPolicy | None = None) -> str:
    """Sorteia até conter todas as classes, o que mantém a distribuição uniforme.

    Inserir um caractere de cada classe em posições fixas e embaralhar criaria viés.
    """
    policy = policy or PasswordPolicy()
    classes = policy.character_classes()
    alphabet = "".join(classes)
    while True:
        password = "".join(secrets.choice(alphabet) for _ in range(policy.length))
        if all(any(char in characters for char in password) for characters in classes):
            return password


def validate_new_master_password(master_password: str, confirmation: str) -> None:
    if len(master_password) < MIN_MASTER_PASSWORD_LENGTH:
        raise InvalidMasterPasswordError(
            f"A senha mestra deve ter ao menos {MIN_MASTER_PASSWORD_LENGTH} caracteres."
        )
    if master_password != confirmation:
        raise InvalidMasterPasswordError("A confirmação não corresponde à senha mestra.")
