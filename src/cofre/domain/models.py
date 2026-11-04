"""Entidades e regras de negócio do cofre."""

from __future__ import annotations

from dataclasses import dataclass, field


class DomainError(Exception):
    """Violação de regra de negócio. A mensagem nunca contém segredos (RN8)."""


class InvalidEntryError(DomainError):
    pass


class DuplicateEntryError(DomainError):
    pass


class EntryNotFoundError(DomainError):
    pass


@dataclass(frozen=True, slots=True)
class Entry:
    service: str
    username: str | None
    password: str = field(repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "service", self.service.strip())
        if self.username is not None:
            object.__setattr__(self, "username", self.username.strip())
        if not self.service:
            raise InvalidEntryError("Informe o serviço.")
        # None é a escolha explícita de "sem usuário"; texto vazio é campo esquecido.
        if self.username == "":
            raise InvalidEntryError("Informe o usuário.")
        if not self.password:
            raise InvalidEntryError("Informe a senha.")

    @property
    def key(self) -> tuple[str, str]:
        return entry_key(self.service, self.username)


def entry_key(service: str, username: str | None) -> tuple[str, str]:
    """Identidade de uma entrada: "GitHub" e "github" são o mesmo serviço (RN1).

    Sem usuário equivale a usuário vazio, que nenhuma entrada com usuário pode ter.
    """
    return service.strip().casefold(), (username or "").strip().casefold()


@dataclass(frozen=True, slots=True)
class Vault:
    """Coleção imutável: alterar gera um novo cofre, que só vale depois de gravado."""

    entries: tuple[Entry, ...] = ()

    def __post_init__(self) -> None:
        keys = [entry.key for entry in self.entries]
        if len(keys) != len(set(keys)):
            raise DuplicateEntryError("Já existe uma entrada para este serviço e usuário.")

    def added(self, entry: Entry) -> Vault:
        return Vault((*self.entries, entry))

    def find(self, service: str, username: str | None) -> Entry:
        key = entry_key(service, username)
        for entry in self.entries:
            if entry.key == key:
                return entry
        raise EntryNotFoundError("Entrada não encontrada.")

    def removed(self, service: str, username: str | None) -> Vault:
        key = entry_key(service, username)
        remaining = tuple(entry for entry in self.entries if entry.key != key)
        if len(remaining) == len(self.entries):
            raise EntryNotFoundError("Entrada não encontrada.")
        return Vault(remaining)

    def sorted_entries(self) -> list[Entry]:
        return sorted(self.entries, key=lambda entry: entry.key)
