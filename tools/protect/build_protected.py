#!/usr/bin/env python3
import os
import subprocess
import sys
import tempfile

_here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _here)
sys.path.insert(0, os.path.join(_here, os.pardir, "harness"))

from encrypt_blob import encrypt_blob
import roundtrip


def build_protected(agent_path: str, out_path: str, key: bytes) -> None:
    protect_dir = os.path.dirname(__file__)
    with tempfile.TemporaryDirectory() as tmp:
        obfuscated_path = os.path.join(tmp, "obfuscated.js")
        subprocess.run(
            [
                "node",
                os.path.join(protect_dir, "obfuscate.mjs"),
                agent_path,
                obfuscated_path,
            ],
            check=True,
        )
        bytecode = roundtrip.compile(obfuscated_path)
        container = encrypt_blob(bytecode, key)
        with open(out_path, "wb") as f:
            f.write(container)


def main():
    if len(sys.argv) != 3:
        print("usage: build_protected.py <agent.js> <out.fpb>", file=sys.stderr)
        sys.exit(1)

    key_path = os.environ.get("FPB_KEY_FILE")
    if not key_path:
        print("error: FPB_KEY_FILE env var must point to a 32-byte key file", file=sys.stderr)
        sys.exit(1)

    with open(key_path, "rb") as f:
        key = f.read()
    if len(key) != 32:
        print("error: key file must contain exactly 32 bytes", file=sys.stderr)
        sys.exit(1)

    build_protected(sys.argv[1], sys.argv[2], key)


if __name__ == "__main__":
    main()
