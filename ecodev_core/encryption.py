"""
Module implementing simple fernet AES128 encryption/decryption
"""
from cryptography.fernet import Fernet

from ecodev_core.settings import SETTINGS


FERNET: Fernet | None = None


def get_fernet():
    global FERNET
    if FERNET is None:
        FERNET = Fernet(SETTINGS.fernet_key.encode())
    return FERNET


def encrypt_value(value: float) -> bytes:
    """
    Encrypt a value using Fernet symmetric encryption.

    Args:
        value: Value to encrypt (will be converted to string)

    Returns:
        Encrypted bytes
    """
    return get_fernet().encrypt(str(value).encode())


def decrypt_value(encrypted: bytes):
    """
    Decrypt an encrypted value and convert to float.

    Args:
        encrypted: Encrypted bytes to decrypt

    Returns:
        Decrypted value as float
    """
    return float(get_fernet().decrypt(encrypted).decode())
