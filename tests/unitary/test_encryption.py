"""
Module testing encryption functionality
"""
from cryptography.fernet import InvalidToken

from ecodev_core import SafeTestCase
from ecodev_core.encryption import decrypt_value
from ecodev_core.encryption import encrypt_value


class EncryptionTest(SafeTestCase):
    """
    Class testing encryption and decryption functions
    """

    def test_encrypt_decrypt_float(self):
        """
        Test encrypting and decrypting a float value
        """
        original_value = 3.14159
        encrypted = encrypt_value(original_value)
        decrypted = decrypt_value(encrypted)
        self.assertEqual(decrypted, original_value)

    def test_decrypt_invalid_data(self):
        """
        Test decrypting invalid encrypted data raises InvalidToken
        """
        invalid_data = b'invalid_encrypted_data'
        with self.assertRaises(InvalidToken):
            decrypt_value(invalid_data)
