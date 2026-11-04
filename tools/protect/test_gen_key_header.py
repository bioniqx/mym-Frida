"""Unit tests for gen_key_header.py (plan Phase-1b Step 10: embedded key header).

Criterion mapping:
- writes subprojects/frida-gum/lib/prot/gumprotkey.h containing
  'static const guint8 gum_prot_key[32] = { ... }' with exactly the 32 key
  bytes in 0x%02x form, wrapped in include guards
  -> test_header_contains_exactly_the_key_bytes
- refuses key files whose length is not 32 bytes with non-zero exit, a clear
  message, and never prints the key bytes to stdout/stderr
  -> test_wrong_length_key_refused_nonzero_without_leaking_bytes
- reports the header path as subprojects/frida-gum/lib/prot/gumprotkey.h
  -> test_header_path_reported_as_documented_relative_path
- README 'Building' documents the one-time key step and that the header is
  git-ignored and regenerated per build/release
  -> test_readme_building_section_documents_one_time_key_step
- the generated header compiles as C
  -> test_generated_header_compiles_as_c
"""
import binascii
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "gen_key_header.py")
README = os.path.join(HERE, "README.md")
HEADER_PATH = "subprojects/frida-gum/lib/prot/gumprotkey.h"


def _run_generator(key_bytes, cwd):
    assert os.path.exists(SCRIPT), "gen_key_header.py is missing"
    key_path = os.path.join(cwd, "key.bin")
    with open(key_path, "wb") as f:
        f.write(key_bytes)
    return subprocess.run(
        [sys.executable, SCRIPT, key_path],
        cwd=cwd,
        capture_output=True,
    )


def test_header_contains_exactly_the_key_bytes():
    key = bytes(range(32))
    with tempfile.TemporaryDirectory() as tmp:
        proc = _run_generator(key, tmp)
        assert proc.returncode == 0, proc.stderr.decode()
        header_path = os.path.join(tmp, HEADER_PATH)
        assert os.path.isfile(header_path)
        with open(header_path) as f:
            text = f.read()
        assert "#ifndef GUM_PROT_KEY_H" in text
        assert "#define GUM_PROT_KEY_H" in text
        assert "#endif" in text
        declaration = "static const guint8 gum_prot_key[32] = {"
        assert declaration in text
        line = text[text.index(declaration):]
        line = line[:line.index("}") + 1]
        inner = line[line.index("{") + 1:line.index("}")]
        parsed = bytes(int(item, 16) for item in inner.split(","))
        assert parsed == key
        assert ", ".join("0x%02x" % b for b in key) in text
        expected_line = "static const guint8 gum_prot_key[32] = { %s };" % (
            ", ".join("0x%02x" % b for b in key),
        )
        assert expected_line in text


def test_wrong_length_key_refused_nonzero_without_leaking_bytes():
    for bad in (b"", os.urandom(16), os.urandom(31), os.urandom(33)):
        with tempfile.TemporaryDirectory() as tmp:
            proc = _run_generator(bad, tmp)
            assert proc.returncode != 0
            out = proc.stdout.decode()
            err = proc.stderr.decode()
            assert err.strip(), "expected a clear refusal message on stderr"
            assert "32" in err
            forbidden = bad + binascii.hexlify(bad)
            if forbidden:
                assert forbidden not in (proc.stdout + proc.stderr)
            assert not os.path.exists(os.path.join(tmp, HEADER_PATH))


def test_header_path_reported_as_documented_relative_path():
    key = os.urandom(32)
    with tempfile.TemporaryDirectory() as tmp:
        proc = _run_generator(key, tmp)
        assert proc.returncode == 0, proc.stderr.decode()
        assert HEADER_PATH in proc.stdout.decode()
        assert os.path.isfile(os.path.join(tmp, HEADER_PATH))


def test_readme_building_section_documents_one_time_key_step():
    assert os.path.exists(README), "tools/protect/README.md is missing"
    with open(README) as f:
        text = f.read()
    assert "## Building" in text
    start = text.index("## Building")
    end = text.find("\n## ", start + 1)
    if end == -1:
        end = len(text)
    section = text[start:end]
    for phrase in (
        "tools/protect/.key",
        "gen_key_header.py",
        "32",
        "git-ignored",
        "regenerated",
    ):
        assert phrase in section, "Building section lacks %r" % phrase


def test_generated_header_compiles_as_c():
    key = os.urandom(32)
    with tempfile.TemporaryDirectory() as tmp:
        proc = _run_generator(key, tmp)
        assert proc.returncode == 0, proc.stderr.decode()
        check_c = os.path.join(tmp, "check.c")
        with open(check_c, "w") as f:
            f.write("#include <stdint.h>\n")
            f.write("typedef uint8_t guint8;\n")
            f.write('#include "gumprotkey.h"\n')
            f.write("int main (void) { return gum_prot_key[0] + gum_prot_key[31]; }\n")
        cc = shutil.which("clang") or shutil.which("cc")
        assert cc, "no C compiler found for the syntax check"
        include_dir = os.path.join(tmp, os.path.dirname(HEADER_PATH))
        compile_proc = subprocess.run(
            [cc, "-fsyntax-only", "-I", include_dir, check_c],
            cwd=tmp,
            capture_output=True,
        )
        assert compile_proc.returncode == 0, compile_proc.stderr.decode()


if __name__ == "__main__":
    test_header_contains_exactly_the_key_bytes()
    test_wrong_length_key_refused_nonzero_without_leaking_bytes()
    test_header_path_reported_as_documented_relative_path()
    test_readme_building_section_documents_one_time_key_step()
    test_generated_header_compiles_as_c()
    print("OK")
