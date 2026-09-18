"""Credential storage tests.

These guard the property the module exists for: LinkedIn credentials live in
the OS keychain and nowhere else. The keychain is replaced with an in-memory
fake, so no test touches the real one.
"""
import builtins

import keyring.errors
import pytest

from bot import credentials


class _FakeKeyring:
    def __init__(self):
        self.store = {}

    def set_password(self, service, key, value):
        self.store[(service, key)] = value

    def get_password(self, service, key):
        return self.store.get((service, key))

    def delete_password(self, service, key):
        if (service, key) not in self.store:
            raise keyring.errors.PasswordDeleteError("missing")
        del self.store[(service, key)]


@pytest.fixture
def fake_keyring(monkeypatch):
    fake = _FakeKeyring()
    monkeypatch.setattr(credentials.keyring, "set_password", fake.set_password)
    monkeypatch.setattr(credentials.keyring, "get_password", fake.get_password)
    monkeypatch.setattr(credentials.keyring, "delete_password", fake.delete_password)
    return fake


def test_save_writes_both_values_to_the_keychain_only(fake_keyring, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(builtins, "input", lambda _prompt: "  me@example.com  ")
    monkeypatch.setattr(credentials.getpass, "getpass", lambda _prompt: "s3cret-value")

    credentials.save_credentials()

    assert fake_keyring.store[("linkedin-bot", "linkedin_email")] == "me@example.com"
    assert fake_keyring.store[("linkedin-bot", "linkedin_password")] == "s3cret-value"
    # Nothing was written to the working directory.
    assert list(tmp_path.iterdir()) == []


def test_password_is_read_with_getpass_not_input(fake_keyring, monkeypatch):
    # input() echoes to the terminal and can land in shell scrollback or a
    # screen recording; getpass does not.
    prompts = []
    monkeypatch.setattr(builtins, "input", lambda prompt: prompts.append(("input", prompt)) or "me@example.com")
    monkeypatch.setattr(credentials.getpass, "getpass", lambda prompt: prompts.append(("getpass", prompt)) or "pw")

    credentials.save_credentials()

    kinds = {kind for kind, prompt in prompts if "password" in prompt.lower()}
    assert kinds == {"getpass"}


def test_password_never_appears_in_stdout(fake_keyring, monkeypatch, capsys):
    monkeypatch.setattr(builtins, "input", lambda _p: "me@example.com")
    monkeypatch.setattr(credentials.getpass, "getpass", lambda _p: "very-distinctive-pw-9481")

    credentials.save_credentials()
    credentials.get_password()

    assert "very-distinctive-pw-9481" not in capsys.readouterr().out


def test_getters_return_stored_values(fake_keyring):
    fake_keyring.set_password("linkedin-bot", "linkedin_email", "me@example.com")
    fake_keyring.set_password("linkedin-bot", "linkedin_password", "pw")
    assert credentials.get_email() == "me@example.com"
    assert credentials.get_password() == "pw"


@pytest.mark.parametrize("getter", [credentials.get_email, credentials.get_password])
def test_missing_credentials_fail_closed_with_a_remedy(fake_keyring, getter):
    # An empty keychain must stop the bot, not let it attempt a login with
    # None and fail somewhere less obvious.
    with pytest.raises(RuntimeError, match="save-credentials"):
        getter()


def test_credentials_exist_requires_both_values(fake_keyring):
    assert credentials.credentials_exist() is False
    fake_keyring.set_password("linkedin-bot", "linkedin_email", "me@example.com")
    assert credentials.credentials_exist() is False
    fake_keyring.set_password("linkedin-bot", "linkedin_password", "pw")
    assert credentials.credentials_exist() is True


def test_delete_removes_both_values(fake_keyring):
    fake_keyring.set_password("linkedin-bot", "linkedin_email", "me@example.com")
    fake_keyring.set_password("linkedin-bot", "linkedin_password", "pw")
    credentials.delete_credentials()
    assert fake_keyring.store == {}


def test_delete_is_idempotent_when_nothing_is_stored(fake_keyring):
    # Rotating credentials on a fresh machine must not crash.
    credentials.delete_credentials()
    credentials.delete_credentials()
    assert fake_keyring.store == {}
