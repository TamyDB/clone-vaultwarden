"""Casos de uso do cofre. É a única porta de entrada da interface para o núcleo."""

from __future__ import annotations

from pathlib import Path

from cofre.domain.models import DomainError, Entry, Vault
from cofre.domain.passwords import validate_new_master_password
from cofre.storage.vault_file import (
    VaultAuthError,
    VaultFormatError,
    VaultKey,
    backup_path,
    decode_vault,
    encode_vault,
    new_vault_key,
    read_vault_file,
    write_copy,
    write_vault_file,
)


class VaultLockedError(DomainError):
    pass


class VaultAlreadyExistsError(DomainError):
    pass


class VaultNotFoundError(DomainError):
    pass


class UnlockFailedError(DomainError):
    pass


class ConfirmationRequiredError(DomainError):
    pass


class BackupError(DomainError):
    pass


class RestoreFailedError(DomainError):
    pass


class VaultService:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._vault: Vault | None = None
        self._key: VaultKey | None = None

    @property
    def vault_exists(self) -> bool:
        return self._path.exists()

    @property
    def is_unlocked(self) -> bool:
        return self._vault is not None

    def create(
        self, master_password: str, confirmation: str, *, acknowledged_no_recovery: bool
    ) -> None:
        if self.vault_exists:
            raise VaultAlreadyExistsError("Já existe um cofre neste local.")
        validate_new_master_password(master_password, confirmation)
        if not acknowledged_no_recovery:
            raise ConfirmationRequiredError(
                "Confirme que está ciente de que a senha mestra não pode ser recuperada."
            )
        key = new_vault_key(master_password)
        self._save(Vault(), key)

    def unlock(self, master_password: str) -> None:
        if not self.vault_exists:
            raise VaultNotFoundError("Nenhum cofre encontrado.")
        try:
            vault, key = decode_vault(read_vault_file(self._path), master_password)
        except (VaultAuthError, VaultFormatError) as error:
            raise UnlockFailedError("Senha incorreta ou arquivo corrompido.") from error
        self._vault, self._key = vault, key

    def lock(self) -> None:
        """Descarta as referências à chave e aos dados; ver limites em docs/ARQUITETURA.md."""
        self._vault = None
        self._key = None

    def entries(self) -> list[Entry]:
        return self._require_vault().sorted_entries()

    def get_password(self, service: str, username: str | None) -> str:
        return self._require_vault().find(service, username).password

    def add_entry(self, service: str, username: str | None, password: str) -> None:
        self._save(self._require_vault().added(Entry(service, username, password)), self._key)

    def update_entry(
        self,
        service: str,
        username: str | None,
        new_service: str,
        new_username: str | None,
        new_password: str,
    ) -> None:
        updated = Entry(new_service, new_username, new_password)
        self._save(self._require_vault().replaced(service, username, updated), self._key)

    def delete_entry(self, service: str, username: str | None, *, confirmed: bool) -> None:
        vault = self._require_vault()
        if not confirmed:
            raise ConfirmationRequiredError("Confirme a exclusão da entrada.")
        self._save(vault.removed(service, username), self._key)

    def export_backup(self, destination: Path) -> None:
        """Copia o arquivo já cifrado: o backup tem a mesma senha mestra do cofre."""
        if not self.vault_exists:
            raise VaultNotFoundError("Nenhum cofre encontrado.")
        if self._is_own_file(destination):
            raise BackupError("Escolha um local diferente do arquivo do cofre.")
        write_copy(destination, read_vault_file(self._path))

    def restore_backup(self, source: Path, master_password: str) -> None:
        """Valida o backup com a senha dele antes de tocar no cofre atual, que vai para o `.bak`."""
        if source.resolve() == self._path.resolve():
            raise BackupError("Escolha um arquivo diferente do cofre atual.")
        blob = read_vault_file(source)
        try:
            decode_vault(blob, master_password)
        except (VaultAuthError, VaultFormatError) as error:
            raise RestoreFailedError("Senha incorreta ou backup inválido.") from error
        write_vault_file(self._path, blob)
        self.lock()

    def _is_own_file(self, other: Path) -> bool:
        own = {self._path.resolve(), backup_path(self._path).resolve()}
        return other.resolve() in own

    def _require_vault(self) -> Vault:
        if self._vault is None:
            raise VaultLockedError("O cofre está bloqueado.")
        return self._vault

    def _save(self, vault: Vault, key: VaultKey) -> None:
        # A memória só muda depois da gravação: se o disco falhar, a tela não mostra
        # uma entrada que não foi salva.
        write_vault_file(self._path, encode_vault(vault, key))
        self._vault, self._key = vault, key
