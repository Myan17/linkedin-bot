"""
Stores and retrieves LinkedIn credentials from macOS Keychain.
Credentials are encrypted by the OS and never written to disk in plaintext.
"""
import getpass
import keyring

_SERVICE = "linkedin-bot"
_EMAIL_KEY = "linkedin_email"
_PASSWORD_KEY = "linkedin_password"


def save_credentials():
    """Prompt the user for credentials and store them in macOS Keychain."""
    print("\nEnter your LinkedIn credentials (stored securely in macOS Keychain):")
    email = input("  LinkedIn email: ").strip()
    password = getpass.getpass("  LinkedIn password: ")

    keyring.set_password(_SERVICE, _EMAIL_KEY, email)
    keyring.set_password(_SERVICE, _PASSWORD_KEY, password)
    print("Credentials saved to Keychain. They will not be stored in any file.")


def get_email() -> str:
    email = keyring.get_password(_SERVICE, _EMAIL_KEY)
    if not email:
        raise RuntimeError(
            "LinkedIn email not found in Keychain.\n"
            "Run `python main.py save-credentials` to store it securely."
        )
    return email


def get_password() -> str:
    password = keyring.get_password(_SERVICE, _PASSWORD_KEY)
    if not password:
        raise RuntimeError(
            "LinkedIn password not found in Keychain.\n"
            "Run `python main.py save-credentials` to store it securely."
        )
    return password


def credentials_exist() -> bool:
    return bool(
        keyring.get_password(_SERVICE, _EMAIL_KEY) and
        keyring.get_password(_SERVICE, _PASSWORD_KEY)
    )


def delete_credentials():
    """Wipe credentials from Keychain (e.g. to rotate them)."""
    try:
        keyring.delete_password(_SERVICE, _EMAIL_KEY)
    except keyring.errors.PasswordDeleteError:
        pass
    try:
        keyring.delete_password(_SERVICE, _PASSWORD_KEY)
    except keyring.errors.PasswordDeleteError:
        pass
    print("Credentials removed from Keychain.")
