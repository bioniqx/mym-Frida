import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from encrypt_blob import encrypt_blob, decrypt_blob


def test_round_trip():
    key = os.urandom(32)
    plain = b"hello"
    container = encrypt_blob(plain, key)
    assert container[:4] == b"FPB1"
    assert len(container) == 4 + 12 + len(plain) + 16
    assert decrypt_blob(container, key) == plain


def test_wrong_key_raises():
    key = os.urandom(32)
    wrong_key = os.urandom(32)
    container = encrypt_blob(b"hello", key)
    raised = False
    try:
        decrypt_blob(container, wrong_key)
    except Exception:
        raised = True
    assert raised


def test_non_32_byte_key_rejected():
    raised = False
    try:
        encrypt_blob(b"hello", os.urandom(16))
    except ValueError:
        raised = True
    assert raised

    raised = False
    try:
        decrypt_blob(b"FPB1" + os.urandom(12) + os.urandom(21), os.urandom(16))
    except ValueError:
        raised = True
    assert raised


def test_bad_magic_rejected():
    key = os.urandom(32)
    raised = False
    try:
        decrypt_blob(b"NOPE" + os.urandom(12) + os.urandom(21), key)
    except ValueError:
        raised = True
    assert raised


if __name__ == "__main__":
    test_round_trip()
    test_wrong_key_raises()
    test_non_32_byte_key_rejected()
    test_bad_magic_rejected()
    print("OK")
