import base64
import os

from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

BLOCK_SIZE_BITS = 128
IV_SIZE_BYTES = 16

def _get_key() -> bytes:
    key_hex = os.getenv("AES_KEY", "")
    try:
        key = bytes.fromhex(key_hex)
    except ValueError as exc:
        raise ValueError("AES_KEY debe ser una cadena hexadecimal válida.") from exc

    if len(key) not in (16, 24, 32):
        raise ValueError(
            "AES_KEY debe ser de 16, 24 o 32 bytes (32, 48 o 64 caracteres hexadecimales)."
        )
    return key


def encrypt_message(plaintext: str) -> str:
    key = _get_key()
    iv = os.urandom(IV_SIZE_BYTES)

    padder = padding.PKCS7(BLOCK_SIZE_BITS).padder()
    padded = padder.update(plaintext.encode("utf-8")) + padder.finalize()

    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(padded) + encryptor.finalize()

    return base64.b64encode(iv + ciphertext).decode("utf-8")


def decrypt_message(token: str) -> str:
    raw = base64.b64decode(token)
    iv, ciphertext = raw[:IV_SIZE_BYTES], raw[IV_SIZE_BYTES:]

    key = _get_key()
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    decryptor = cipher.decryptor()
    padded = decryptor.update(ciphertext) + decryptor.finalize()

    unpadder = padding.PKCS7(BLOCK_SIZE_BITS).unpadder()
    plaintext = unpadder.update(padded) + unpadder.finalize()
    return plaintext.decode("utf-8")
