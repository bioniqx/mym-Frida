import os
import subprocess
import sys
import tempfile


def test_build_protected_produces_fpb():
    key = os.urandom(32)
    with tempfile.TemporaryDirectory() as tmp:
        key_path = os.path.join(tmp, "key.bin")
        with open(key_path, "wb") as f:
            f.write(key)

        agent_path = os.path.join(tmp, "agent.js")
        with open(agent_path, "w") as f:
            f.write("console.log('hello');\n")

        out_path = os.path.join(tmp, "agent.fpb")

        env = dict(os.environ)
        env["FPB_KEY_FILE"] = key_path

        script = os.path.join(os.path.dirname(__file__), "build_protected.py")
        result = subprocess.run(
            [sys.executable, script, agent_path, out_path],
            env=env,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr

        with open(out_path, "rb") as f:
            data = f.read()
        assert data[:4] == b"FPB1"


def test_missing_fpb_key_file_exits_1():
    with tempfile.TemporaryDirectory() as tmp:
        agent_path = os.path.join(tmp, "agent.js")
        with open(agent_path, "w") as f:
            f.write("console.log('hello');\n")

        out_path = os.path.join(tmp, "agent.fpb")

        env = dict(os.environ)
        env.pop("FPB_KEY_FILE", None)

        script = os.path.join(os.path.dirname(__file__), "build_protected.py")
        result = subprocess.run(
            [sys.executable, script, agent_path, out_path],
            env=env,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1, result.stderr
        assert "FPB_KEY_FILE" in result.stderr


def test_non_32_byte_key_file_exits_1():
    with tempfile.TemporaryDirectory() as tmp:
        key_path = os.path.join(tmp, "key.bin")
        with open(key_path, "wb") as f:
            f.write(os.urandom(16))

        agent_path = os.path.join(tmp, "agent.js")
        with open(agent_path, "w") as f:
            f.write("console.log('hello');\n")

        out_path = os.path.join(tmp, "agent.fpb")

        env = dict(os.environ)
        env["FPB_KEY_FILE"] = key_path

        script = os.path.join(os.path.dirname(__file__), "build_protected.py")
        result = subprocess.run(
            [sys.executable, script, agent_path, out_path],
            env=env,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1, result.stderr
        assert "32" in result.stderr


if __name__ == "__main__":
    test_build_protected_produces_fpb()
    test_missing_fpb_key_file_exits_1()
    test_non_32_byte_key_file_exits_1()
    print("OK")
