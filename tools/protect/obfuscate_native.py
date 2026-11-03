#!/usr/bin/env python3
"""Run native_core.c through Tigress source obfuscation for the current OS/arch."""

import argparse
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ENVIRONMENTS = {
    ("Linux", "x86_64"): "x86_64:Linux:Gcc:4.6",
    ("Linux", "aarch64"): "arm64:Linux:Gcc:4.6",
    ("Darwin", "x86_64"): "x86_64:Darwin:Clang:5.1",
    ("Darwin", "arm64"): "arm64:Darwin:Clang:5.1",
    ("Windows", "x86_64"): "x86_64:Windows:Gcc:4.6",
    ("Windows", "AMD64"): "x86_64:Windows:Gcc:4.6",
}


def detect_environment():
    system = platform.system()
    machine = platform.machine()
    key = (system, machine)
    if key not in ENVIRONMENTS:
        sys.exit(
            f"obfuscate_native.py: no Tigress --Environment mapping for "
            f"{system}/{machine}"
        )
    return ENVIRONMENTS[key]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path, help="Path to native_core.c")
    parser.add_argument("output", type=Path, help="Path to write native_core.obf.c")
    args = parser.parse_args()

    if shutil.which("tigress") is None:
        sys.exit(
            "obfuscate_native.py: 'tigress' not found on PATH. Install Tigress "
            "(it has its own license and is not bundled with this repo) and "
            "ensure the 'tigress' binary is on PATH before building with "
            "-Dprot_obfuscate=true."
        )

    environment = detect_environment()
    args.output.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "tigress",
        f"--Environment={environment}",
        "--Transform=Flatten", "--Functions=*",
        "--Transform=AddOpaque", "--Functions=*",
        "--Transform=EncodeStrings", "--Functions=*",
        f"--out={args.output}",
        str(args.input),
    ]
    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    main()
