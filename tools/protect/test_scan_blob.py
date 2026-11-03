"""Unit tests for scan_blob.py (plan T04, Steps 1-4).

Gate evidence mapping (plan T04 Steps 5-10, Steps 8 and 10 pin the exit
codes asserted here): the obfuscated-sample blob must scan CLEAN for the
original local identifier and ROUNDTRIP_OK (exit 0), while the plain blob
must come back LEAKED: ROUNDTRIP_OK (exit 1). These tests pin the scanner
contract those gate steps rely on.
"""
import os
import subprocess
import sys
import tempfile

SCRIPT = os.path.join(os.path.dirname(__file__), "scan_blob.py")


def run_scan(blob_bytes, tokens):
    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(blob_bytes)
        blob_path = f.name
    try:
        args = [sys.executable, SCRIPT, blob_path, "--forbid"] + tokens
        return subprocess.run(args, capture_output=True, text=True)
    finally:
        os.remove(blob_path)


def test_detects_utf8_leak():
    blob = b"prefix_bytes" + "secretName".encode("utf-8") + b"_suffix_bytes"
    result = run_scan(blob, ["secretName"])
    assert result.returncode == 1, (
        f"expected exit 1, got {result.returncode}: "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert "secretName" in result.stdout, f"expected leaked token in output, got: {result.stdout!r}"


def test_detects_utf16le_leak():
    blob = b"prefix_bytes" + "secretName".encode("utf-16-le") + b"_suffix_bytes"
    result = run_scan(blob, ["secretName"])
    assert result.returncode == 1, (
        f"expected exit 1, got {result.returncode}: "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert "secretName" in result.stdout, f"expected leaked token in output, got: {result.stdout!r}"


def test_clean_blob_passes():
    blob = b"nothing_interesting_here_at_all"
    result = run_scan(blob, ["secretName"])
    assert result.returncode == 0, (
        f"expected exit 0, got {result.returncode}: "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )


if __name__ == "__main__":
    test_detects_utf8_leak()
    test_detects_utf16le_leak()
    test_clean_blob_passes()
    print("ALL TESTS PASSED")
