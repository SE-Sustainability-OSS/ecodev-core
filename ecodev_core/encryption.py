"""
Module implementing simple fernet AES128 encryption/decryption
"""
from cryptography.fernet import Fernet
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict

from ecodev_core.settings import SETTINGS


class EncryptionConf(BaseSettings):
    """
    Simple authentication configuration class
    """
    fernet_key: str = ''
    model_config = SettingsConfigDict(env_file='.env')


SECRET_KEY = SETTINGS.fernet_key or EncryptionConf().fernet_key  # type: ignore[attr-defined]
FERNET = Fernet(SECRET_KEY.encode())


def encrypt_value(value):
    """
    Encrypt a value using Fernet symmetric encryption.

    Args:
        value: Value to encrypt (will be converted to string)

    Returns:
        Encrypted bytes
    """
    return FERNET.encrypt(str(value).encode())


def decrypt_value(encrypted):
    """
    Decrypt an encrypted value and convert to float.

    Args:
        encrypted: Encrypted bytes to decrypt

    Returns:
        Decrypted value as float
    """
    return float(FERNET.decrypt(encrypted).decode())
