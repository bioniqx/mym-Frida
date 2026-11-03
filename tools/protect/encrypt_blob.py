import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

MAGIC = b"FPB1"
NONCE_LEN = 12


def encrypt_blob(plain: bytes, key: bytes) -> bytes:
    if len(key) != 32:
        raise ValueError("key must be 32 bytes")
    nonce = os.urandom(NONCE_LEN)
    ciphertext = AESGCM(key).encrypt(nonce, plain, None)
    return MAGIC + nonce + ciphertext


def decrypt_blob(container: bytes, key: bytes) -> bytes:
    if len(key) != 32:
        raise ValueError("key must be 32 bytes")
    if container[:4] != MAGIC:
        raise ValueError("bad magic: not an FPB1 container")
    nonce = container[4:4 + NONCE_LEN]
    ciphertext = container[4 + NONCE_LEN:]
    return AESGCM(key).decrypt(nonce, ciphertext, None)
