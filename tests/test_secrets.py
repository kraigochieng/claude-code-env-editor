import stat

import pytest

from claude_code_env_editor.secrets import SecretsError, SecretStore


def store(tmp_path, passphrase="pw"):
    return SecretStore(tmp_path / "vault.enc", passphrase=lambda: passphrase, use_keyring=False)


def test_round_trip(tmp_path):
    s = store(tmp_path)
    s.set("KEY", "sk-secret-value")
    assert s.get("KEY") == "sk-secret-value"


def test_vault_file_holds_no_plain_text(tmp_path):
    store(tmp_path).set("KEY", "sk-secret-value")
    assert b"sk-secret-value" not in (tmp_path / "vault.enc").read_bytes()


def test_vault_mode_is_0600(tmp_path):
    store(tmp_path).set("KEY", "v")
    assert stat.S_IMODE((tmp_path / "vault.enc").stat().st_mode) == 0o600


def test_wrong_passphrase_fails(tmp_path):
    store(tmp_path).set("KEY", "v")
    with pytest.raises(SecretsError):
        store(tmp_path, passphrase="other").get("KEY")


def test_delete(tmp_path):
    s = store(tmp_path)
    s.set("KEY", "v")
    s.delete("KEY")
    assert s.get("KEY") is None


def test_missing_passphrase_source_fails(tmp_path):
    with pytest.raises(SecretsError):
        SecretStore(tmp_path / "vault.enc", use_keyring=False).set("K", "v")


def test_missing_vault_reads_empty(tmp_path):
    assert store(tmp_path).get("KEY") is None
