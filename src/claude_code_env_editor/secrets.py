"""Store secrets in the OS keyring. Fall back to a passphrase-encrypted file."""

from __future__ import annotations

import base64
import json
import os
import tempfile
from pathlib import Path
from typing import Callable

SERVICE = "claude-code-env-editor"
VAULT_NAME = "vault.enc"
_SALT_LEN = 16


class SecretsError(Exception):
    """The secret store failed or the passphrase is wrong."""


def _keyring():
    """Return the keyring module when a real backend exists, else None."""
    try:
        import keyring
        from keyring.backends import fail
    except ImportError:
        return None
    return None if isinstance(keyring.get_keyring(), fail.Keyring) else keyring


def keyring_available() -> bool:
    return _keyring() is not None


def _fernet(passphrase: str, salt: bytes):
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

    key = Scrypt(salt=salt, length=32, n=2**15, r=8, p=1).derive(passphrase.encode())
    return Fernet(base64.urlsafe_b64encode(key))


def default_vault_path() -> Path:
    base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / SERVICE / VAULT_NAME


class SecretStore:
    """Save and load secrets by name. A name is one variable in one config directory."""

    def __init__(
        self,
        vault_path: Path | None = None,
        passphrase: Callable[[], str] | None = None,
        use_keyring: bool = True,
    ) -> None:
        self._vault = vault_path or default_vault_path()
        self._ask = passphrase
        self._keyring = _keyring() if use_keyring else None

    @property
    def backend(self) -> str:
        return "keyring" if self._keyring else "encrypted-file"

    def set(self, name: str, value: str) -> None:
        if self._keyring:
            self._keyring.set_password(SERVICE, name, value)
            return
        data = self._read_vault()
        data[name] = value
        self._write_vault(data)

    def get(self, name: str) -> str | None:
        if self._keyring:
            return self._keyring.get_password(SERVICE, name)
        return self._read_vault().get(name)

    def delete(self, name: str) -> None:
        if self._keyring:
            try:
                self._keyring.delete_password(SERVICE, name)
            except Exception:  # the entry does not exist
                pass
            return
        data = self._read_vault()
        if data.pop(name, None) is not None:
            self._write_vault(data)

    def _passphrase(self) -> str:
        if self._ask is None:
            raise SecretsError("No OS keyring found and no passphrase source set.")
        value = self._ask()
        if not value:
            raise SecretsError("The passphrase is empty.")
        return value

    def _read_vault(self) -> dict[str, str]:
        if not self._vault.exists():
            return {}
        raw = self._vault.read_bytes()
        salt, token = raw[:_SALT_LEN], raw[_SALT_LEN:]
        from cryptography.fernet import InvalidToken

        try:
            return json.loads(_fernet(self._passphrase(), salt).decrypt(token))
        except InvalidToken as exc:
            raise SecretsError("The passphrase is wrong, or the vault file is damaged.") from exc

    def _write_vault(self, data: dict[str, str]) -> None:
        salt = self._vault.read_bytes()[:_SALT_LEN] if self._vault.exists() else os.urandom(_SALT_LEN)
        token = _fernet(self._passphrase(), salt).encrypt(json.dumps(data).encode())
        self._vault.parent.mkdir(parents=True, exist_ok=True)
        os.chmod(self._vault.parent, 0o700)
        fd, tmp = tempfile.mkstemp(dir=self._vault.parent, prefix=".vault-", suffix=".tmp")
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(salt + token)
            os.chmod(tmp, 0o600)
            os.replace(tmp, self._vault)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise
