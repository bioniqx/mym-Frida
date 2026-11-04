#!/usr/bin/env python3
"""Compile a JS agent to QuickJS bytecode, run the bytecode, and print the result.

Usage:
    python tools/harness/roundtrip.py <path-to-agent.js>

Exits 0 iff the agent's marker equals "ROUNDTRIP_OK".

Known transient (macOS, custom build-tree Frida): the first attach after the
build can die inside frida-helper, surfacing as frida.PermissionDeniedError
with "frida-helper appears to have crashed" in the message. This is an
environmental race, not a logic failure: compile() and run() retry the whole
attach/compile-or-run phase after a 120 s cooldown, at most 3 total attempts,
before letting the error propagate. Nothing else is caught.
"""
import glob
import json
import os
import subprocess
import sys
import tempfile
import threading
import time

import frida

MESSAGE_TIMEOUT_SECONDS = 30
HELPER_CRASH_RETRY_SECONDS = 120
MAX_ATTEMPTS = 3

_DARWIN_DUMMY_PATH = None

_DUMMY_C_SOURCE = """#include <unistd.h>

int main(void) {
    for (;;) {
        sleep(60);
    }
}
"""

_DUMMY_ENTITLEMENTS = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>com.apple.security.get-task-allow</key>
    <true/>
</dict>
</plist>
"""


def _disable_external_helper():
    # On macOS, frida-core's external frida-helper gets killed by the system
    # on task_for_pid under SIP (it is only ad-hoc signed). The build tree
    # contains several copies of it (the plain one, meson intermediate dirs,
    # and the arch-support bundles); every copy must be hidden or frida-core
    # picks another one and uses the doomed external attach path. Renaming
    # makes frida-core fall back to the in-process attach path, matching the
    # official wheels. Idempotent: once every copy is renamed, this is a
    # no-op.
    frida_core_dir = os.path.normpath(os.path.join(
        os.path.dirname(frida.__file__), "..", "..", "frida-core"))
    helper_patterns = [
        os.path.join("src", "frida-helper"),
        os.path.join("src", "*", "frida-helper"),
        os.path.join("compat", "arch-support.bundle.p", "*", "src", "frida-helper"),
    ]
    for pattern in helper_patterns:
        for helper_path in glob.glob(os.path.join(frida_core_dir, pattern)):
            disabled_path = helper_path + ".disabled"
            if os.path.exists(disabled_path):
                os.remove(disabled_path)
            os.rename(helper_path, disabled_path)


def _build_entitled_dummy():
    # Attach targets must carry com.apple.security.get-task-allow; a plain
    # interpreter child does not (SIP denies task ports for platform
    # binaries even to their own parent). Build a tiny ad-hoc signed dummy
    # once per process and cache it at module level.
    global _DARWIN_DUMMY_PATH
    if _DARWIN_DUMMY_PATH is not None and os.path.exists(_DARWIN_DUMMY_PATH):
        return _DARWIN_DUMMY_PATH
    build_dir = tempfile.gettempdir()
    base = "frida_roundtrip_dummy-%d" % os.getpid()
    src_path = os.path.join(build_dir, base + ".c")
    plist_path = os.path.join(build_dir, base + ".entitlements")
    bin_path = os.path.join(build_dir, base)
    with open(src_path, "w", encoding="utf-8") as f:
        f.write(_DUMMY_C_SOURCE)
    with open(plist_path, "w", encoding="utf-8") as f:
        f.write(_DUMMY_ENTITLEMENTS)
    subprocess.run(["clang", "-o", bin_path, src_path], check=True)
    subprocess.run(
        ["codesign", "--force", "-s", "-", "--entitlements", plist_path, bin_path],
        check=True,
    )
    _DARWIN_DUMMY_PATH = bin_path
    return bin_path


def _spawn_dummy_process():
    if sys.platform == "win32":
        cmd = ["cmd", "/c", "timeout", "/t", "600"]
    elif sys.platform == "darwin":
        cmd = [_build_entitled_dummy()]
    else:
        cmd = [sys.executable, "-c", "import time;time.sleep(600)"]
    return subprocess.Popen(cmd)


def _is_transient_helper_crash(exc):
    return "frida-helper appears to have crashed" in str(exc)


def compile(source_path: str) -> bytes:
    _disable_external_helper()
    with open(source_path, "r", encoding="utf-8") as f:
        source = f.read()
    device = frida.get_local_device()
    attempts = 0
    while True:
        attempts += 1
        proc = _spawn_dummy_process()
        try:
            session = device.attach(proc.pid)
            try:
                return session.compile_script(source, name="agent")
            finally:
                session.detach()
        except frida.PermissionDeniedError as exc:
            if attempts >= MAX_ATTEMPTS or not _is_transient_helper_crash(exc):
                raise
            time.sleep(HELPER_CRASH_RETRY_SECONDS)
        finally:
            proc.kill()
            proc.wait()


def run(bytecode: bytes) -> str:
    _disable_external_helper()
    device = frida.get_local_device()
    attempts = 0
    while True:
        attempts += 1
        proc = _spawn_dummy_process()
        payload_holder = {}
        received = threading.Event()

        def on_message(message, data):
            if message["type"] == "send":
                payload_holder["payload"] = message["payload"]
                received.set()

        try:
            session = device.attach(proc.pid)
            try:
                script = session.create_script_from_bytes(bytecode)
                script.on("message", on_message)
                script.load()
                if not received.wait(MESSAGE_TIMEOUT_SECONDS):
                    raise TimeoutError(
                        "no message received from agent within %s seconds" % MESSAGE_TIMEOUT_SECONDS
                    )
                payload = payload_holder["payload"]
                if isinstance(payload, dict) and "marker" in payload:
                    return payload["marker"]
                return json.dumps(payload)
            finally:
                session.detach()
        except frida.PermissionDeniedError as exc:
            if attempts >= MAX_ATTEMPTS or not _is_transient_helper_crash(exc):
                raise
            time.sleep(HELPER_CRASH_RETRY_SECONDS)
        finally:
            proc.kill()
            proc.wait()


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: roundtrip.py <path-to-agent.js>", file=sys.stderr)
        return 2
    source_path = sys.argv[1]
    bytecode = compile(source_path)
    print("bytecode: %d bytes, first byte 0x%02x" % (len(bytecode), bytecode[0]),
          file=sys.stderr)
    marker = run(bytecode)
    print(marker)
    return 0 if marker == "ROUNDTRIP_OK" else 1


if __name__ == "__main__":
    sys.exit(main())
