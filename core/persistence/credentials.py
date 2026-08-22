"""API key storage backed by the Windows Credential Manager.

The key never touches config.json, the database or the log file. If the
platform keyring is unavailable, an environment variable is accepted as a
development fallback and nothing is persisted.
"""
from __future__ import annotations

import os

from core.utils.constants import KEYRING_SERVICE, KEYRING_USERNAME
from core.utils.logger import get_logger

log = get_logger("credentials")

ENV_VAR = "OPENAI_API_KEY"


def get_api_key() -> str | None:
    """Return the stored key, falling back to the environment."""
    try:
        import keyring

        key = keyring.get_password(KEYRING_SERVICE, KEYRING_USERNAME)
        if key:
            return key.strip()
    except Exception:  # a locked or missing keyring must not stop startup
        log.warning("Credential store unavailable; falling back to the environment")

    env_key = os.environ.get(ENV_VAR)
    return env_key.strip() if env_key else None


def set_api_key(key: str) -> bool:
    """Store the key securely. Returns False when it could not be saved."""
    key = (key or "").strip()
    if not key:
        return delete_api_key()
    try:
        import keyring

        keyring.set_password(KEYRING_SERVICE, KEYRING_USERNAME, key)
        log.info("API key saved to the credential store")
        return True
    except Exception:
        log.exception("Could not save the API key")
        return False


def delete_api_key() -> bool:
    try:
        import keyring

        keyring.delete_password(KEYRING_SERVICE, KEYRING_USERNAME)
        log.info("API key removed from the credential store")
        return True
    except Exception:
        # Deleting a key that was never stored is not an error worth surfacing.
        return False


def has_api_key() -> bool:
    return bool(get_api_key())


def masked_api_key() -> str:
    """A display form that never reveals the key."""
    key = get_api_key()
    if not key:
        return ""
    return f"{key[:3]}...{key[-4:]}" if len(key) > 12 else "*" * len(key)
