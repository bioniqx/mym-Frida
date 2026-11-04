# Frida Agent White-Box Hardening — Implementation Plan

> **Execution note:** This plan is self-contained and tool-agnostic. Any AI
> agent or human engineer can execute it with only a shell, a code editor,
> and git. No specific AI product, skill, or plugin is required. Follow the
> Execution Protocol below.

**Goal:** Ship the strongest realistically-achievable protection for a Frida QuickJS
bytecode agent under a full white-box desktop threat model, delivered in phases where the
early phases already produce meaningful, verifiable protection.

**Architecture:** A *custom Frida build* is the trust root. Off-the-shelf reverse
engineering is defeated by (a) obfuscating the JS before compilation, (b) permuting the
QuickJS opcode numbering in a pinned QuickJS fork, and (c) encrypting the compiled bytecode
blob and decrypting it only in memory inside the custom Frida. Durable protection against a
binary-holding attacker comes later from moving the agent's logic into an obfuscated native
core statically linked into the custom Frida (this plan builds the *scaffolding* for that),
and ultimately a deep opcode-virtualization VM (framed, later phase).

**Tech Stack:** Frida (frida-gum GumJS QuickJS backend, frida-core, frida-python), a pinned
QuickJS fork (Bellard, `2024-01-13`, `CONFIG_BIGNUM`), Meson/Ninja, C, Python 3 (build
tooling + harness via the `frida` Python bindings), Node/JS (`javascript-obfuscator`),
Tigress (native-code obfuscator, later phase toolchain).

## Execution Protocol (for any AI agent or human engineer)

1. Execute tasks in ID order (T01, T02, …). A task may start only when every
   task in its **Depends** list is complete.
2. Tasks marked `[P]` touch disjoint files and have no incomplete
   dependencies: an orchestrator that supports parallel workers MAY run them
   concurrently; a single agent simply runs them in ID order. Never run two
   tasks that modify the same file at the same time.
3. Within a task, execute steps top to bottom. Mark each checkbox `- [x]`
   when done — the checkboxes are the progress ledger; to resume an
   interrupted run, continue from the first unchecked step.
4. Run every command exactly as written and compare the output to the stated
   Expected result. On mismatch, stop and fix before continuing — never
   proceed past a failing step.
5. Code blocks are the implementation — copy them verbatim. Signatures in
   each task's **Interfaces** block are contracts with other tasks: do not
   rename, reorder parameters, or change types.
6. Commit exactly where the plan says to commit, with the given message.
   Never batch commits across tasks.
7. Global Constraints below apply to every task.
8. If anything is ambiguous, missing, or contradicts the codebase, STOP and
   ask the requester. Do not invent behavior.

## Global Constraints

- **Threat model = full white-box desktop** (Linux, Windows, macOS). The attacker holds
  the custom Frida binary + the protected artifact, controls the OS, and can run a
  debugger / a second Frida / a memory dumper. Never rely on a bypassable runtime gate as
  a real barrier; invest in raising *comprehension cost*.
- **A custom Frida build is required** to run any protected artifact. Protected artifacts
  are bound to the exact QuickJS build and must be rebuilt when Frida is bumped.
- **Pinned QuickJS:** Bellard's fork `frida/quickjs`, version `2024-01-13`
  (commit `080f16a095397ebcded3278385e33d39573afa0d`), built with `bignum=true`
  (`CONFIG_BIGNUM`) and `libc=false` — matching `subprojects/frida-gum/meson.build`. Do not
  change these build options. Work happens on a *forked copy* of this repo, re-pinned in
  `subprojects/frida-gum/subprojects/quickjs.wrap`.
- **Bytecode is QuickJS-only.** The V8 backend refuses both bytecode compile and load. All
  work targets the QJS runtime.
- **Keys and the opcode-permutation seed are unique per build/release** — never a single
  reused value (that would be break-once-run-everywhere). Default key handling is
  **embedded in the custom binary** (offline). Server-tethered keys are a separate spec.
- **Native core (later phase) is statically linked into the custom Frida binary**, never
  shipped as a standalone `.so`/`.dylib`/`.dll`; integrity rides on the binary signature,
  so no separate at-rest encryption for it.
- **Two-tier validation.** Phases 0 / 1a / 1b pass on a *standard-tooling* bar (off-the-shelf
  QuickJS disassembler fails; agent runs; strings absent). Phases 2 / 3 require a *white-box
  red-team* bar (binary patching, dispatch/VM reversing, RAM dump; time-boxed) — a
  standard-tooling red-team does NOT validate them.
- **Code in files is English.** Follow `CONTRIBUTING.md` per-language rules: C and Vala for
  `frida-gum`/QuickJS edits (high-level-first function ordering, project brace/indent
  style); Python and JS for tooling.
- **Out of scope here:** L2 deep VM (framed, later), L5 anti-tamper (later), L6 white-box /
  server-tethered keys (no crypto keys assumed → excluded).
- **Secrets never committed.** Per-build keys/seeds are generated at build time and written
  only to git-ignored paths; never hard-code a key or seed into a tracked file.

---

## File Structure

New tooling lives at the repo root under `tools/protect/` and `tools/harness/` (alongside
the existing `tools/ensure-submodules.py`). Edits to Frida internals happen in the
`frida-gum` submodule and the QuickJS fork.

- `tools/harness/sample_agent.js` — a small representative JS agent used as the test subject
  end-to-end (T02).
- `tools/harness/roundtrip.py` — Python harness: compile a JS agent to QuickJS bytecode and
  load it back via the `frida` bindings, asserting behaviour (T02).
- `tools/protect/obfuscate.mjs` — JS-source obfuscation step (`javascript-obfuscator`) run
  before compilation (T03).
- `tools/protect/package.json` — pins `javascript-obfuscator` for the obfuscation step (T03).
- `tools/protect/scan_blob.py` — leak scanner: asserts given identifier/string tokens are
  absent from a compiled blob (T04).
- `tools/protect/opcode_permute.py` — deterministic opcode-order permutation generator,
  seeded per build, that rewrites the fork's `quickjs-opcode.h` ordering (T05).
- `tools/protect/encrypt_blob.py` — AEAD encryption of a bytecode blob with a per-build key,
  emitting the container the runtime expects (T07).
- `tools/protect/build_protected.py` — one-command orchestrator wiring obfuscate → compile →
  encrypt into a single shippable artifact (T07).
- QuickJS fork: `quickjs-opcode.h` (opcode ordering — T05), and the fork build regen it
  drives.
- `subprojects/frida-gum/subprojects/quickjs.wrap` — re-pin to the owner's fork (T01).
- `subprojects/frida-gum/bindings/gumjs/gumquickscriptbackend.c` — decrypt-before-read hook
  on the bytecode load path (T08); native-core registration hook (T09).
- `subprojects/frida-gum/lib/prot/` (new) — the statically-linked native-core skeleton
  (`native_core.c` / `native_core.h`) + its `meson.build` (T09), obfuscated per-OS (T10).
- `docs/superpowers/plans/2026-09-07-frida-agent-whitebox-hardening.md` — this plan.

---

## Contract Table

| Task | Name | Depends | [P] | Files | Produces / Consumes (exact) |
|---|---|---|---|---|---|
| T01 | Fork & pin QuickJS; custom Frida build bring-up | — |  | `subprojects/frida-gum/subprojects/quickjs.wrap`; `tools/protect/README.md` (build steps) | **Produces:** a reproducible custom Frida build from the owner's QuickJS fork; documented commands `python tools/ensure-submodules.py frida-core frida-python`, `./configure -Dfrida_python=enabled`, `make`. **Consumes:** — |
| T02 | Bytecode round-trip harness + sample agent | T01 |  | Create `tools/harness/sample_agent.js`, `tools/harness/roundtrip.py` | **Produces:** `roundtrip.py` CLI `compile(source_path)->bytes` and `run(bytecode: bytes)->str` using `frida` Python bindings (`session.compile_script`, `session.create_script_from_bytes`); exit 0 on match. **Consumes:** custom build from T01 |
| T03 | JS-source obfuscation step (L4) | T02 | [P] | Create `tools/protect/obfuscate.mjs`, `tools/protect/package.json` | **Produces:** CLI `node tools/protect/obfuscate.mjs <in.js> <out.js>` → obfuscated JS (identifier renaming + string-array encryption). **Consumes:** sample agent from T02 |
| T04 | Blob leak-scan tool + Phase-1a gate (L4) | T03 |  | Create `tools/protect/scan_blob.py` | **Produces:** CLI `python tools/protect/scan_blob.py <blob> --forbid <token>...` exit 1 if any token found. **Consumes:** `obfuscate.mjs` (T03), `roundtrip.compile` (T02) |
| T05 | QuickJS opcode permutation in the fork (L3) | T01 | [P] | Create `tools/protect/opcode_permute.py`; modify fork `quickjs-opcode.h` | **Produces:** `opcode_permute.py --seed <hex>` rewrites `DEF(...)` ordering deterministically; a permuted custom build. **Consumes:** fork from T01 |
| T06 | Stock-disassembler-fails validation (L3 gate) | T05, T02 |  | Create `tools/protect/verify_disasm.sh` | **Produces:** script that builds a stock QuickJS `2024-01-13` (`CONFIG_BIGNUM`) reader and asserts it fails/mis-decodes the permuted blob while the custom Frida runs it. **Consumes:** permuted build (T05), `roundtrip` (T02) |
| T07 | AEAD bytecode encryption + build orchestrator (L3) | T02 | [P] | Create `tools/protect/encrypt_blob.py`, `tools/protect/build_protected.py` | **Produces:** container format `MAGIC(4)=FPB1 \|\| nonce(12) \|\| ciphertext`; `encrypt_blob(plain: bytes, key: bytes)->bytes` (AES-256-GCM); `build_protected.py <agent.js> <out.fpb>` = obfuscate→compile→encrypt. **Consumes:** `obfuscate.mjs` (T03), `roundtrip.compile` (T02) |
| T08 | GumJS decrypt-before-read hook + Phase-1b e2e gate (L3) | T07, T01 |  | Modify `subprojects/frida-gum/bindings/gumjs/gumquickscriptbackend.c` | **Produces:** on the bytecode load path, detect the `FPB1` container and decrypt in memory before `JS_ReadObject`; C helper `static GBytes * gum_prot_decrypt (const guint8 * data, gsize size)`. **Consumes:** container format + key from T07 |
| T09 | Native-core skeleton + static link + GumJS glue (L1 scaffolding) | T01 | [P] | Create `subprojects/frida-gum/lib/prot/native_core.c`, `native_core.h`, `meson.build`; modify `subprojects/frida-gum/bindings/gumjs/gumquickscriptbackend.c` | **Produces:** C entry `int gum_prot_native_entry (const char * op, const char * arg, char * out, size_t out_len)` compiled INTO the frida-gum library (static, no separate module) and reachable from a JS shim via a global `ProtNative.call(op, arg)->string`. **Consumes:** build from T01 |
| T10 | Per-OS native obfuscation (Tigress) + Phase-2a gate (L1) | T09 |  | Create `tools/protect/obfuscate_native.py`; modify `subprojects/frida-gum/lib/prot/meson.build` | **Produces:** per-OS Tigress pass over `native_core.c` wired into the build; validation that a JS shim reaches the native core and `Process.enumerateModules()` shows no extra module. **Consumes:** native core + glue from T09 |

---
### T01: Fork & pin QuickJS; custom Frida build bring-up

**Depends:** —

**Files:**
- Create: `tools/protect/README.md`
- Modify: `subprojects/frida-gum/subprojects/quickjs.wrap`

**Interfaces:**
- Consumes: —
- Produces: a reproducible custom Frida build built from the owner's QuickJS fork, with documented commands.

**Constraints:**
- Full white-box desktop threat model (Linux/Windows/macOS); this custom build is required to run protected artifacts.
- QuickJS pin: Bellard fork `frida/quickjs`, version `2024-01-13`, commit `080f16a095397ebcded3278385e33d39573afa0d`, options `bignum=true` (CONFIG_BIGNUM) and `libc=false`. Do not change these options.
- Code and docs are in English; follow `CONTRIBUTING.md`. Never commit keys or seeds.
- All commands below run from the root of the `frida` repository unless a `cd` is shown. Wherever `OWNER` appears, replace it with the actual GitHub account that owns the QuickJS fork, in every command.

- [ ] **Step 1: Clone upstream QuickJS at the pinned commit into a scratch directory**
```sh
git clone https://github.com/frida/quickjs.git /tmp/quickjs-fork-source
cd /tmp/quickjs-fork-source
git checkout 080f16a095397ebcded3278385e33d39573afa0d
cd -
```
Expected: the `git checkout` output ends with a line like `HEAD is now at 080f16a0 ...`, confirming the pinned commit is checked out.

- [ ] **Step 2: Create the fork on GitHub**
Open `https://github.com/frida/quickjs` in a browser and click "Fork" to create `https://github.com/OWNER/quickjs.git` under your own account. This is a one-time manual step; there is no shell command for it.

- [ ] **Step 3: Push the pinned commit to the fork**
```sh
cd /tmp/quickjs-fork-source
git push https://github.com/OWNER/quickjs.git 080f16a095397ebcded3278385e33d39573afa0d:refs/heads/main
cd -
```
Run: `git ls-remote https://github.com/OWNER/quickjs.git 080f16a095397ebcded3278385e33d39573afa0d`
Expected: prints a line starting with `080f16a095397ebcded3278385e33d39573afa0d` followed by `refs/heads/main`, confirming the pinned commit now exists on the fork.

- [ ] **Step 4: Confirm the wrap file still points at upstream (baseline, before the change)**
Run: `grep -n 'url' subprojects/frida-gum/subprojects/quickjs.wrap`
Expected: `2:url = https://github.com/frida/quickjs.git`

- [ ] **Step 5: Repoint the wrap file at the fork**
```sh
cat > subprojects/frida-gum/subprojects/quickjs.wrap <<'EOF'
[wrap-git]
url = https://github.com/OWNER/quickjs.git
revision = 080f16a095397ebcded3278385e33d39573afa0d
depth = 1

[provide]
dependency_names = quickjs
EOF
```

- [ ] **Step 6: Verify the wrap file now points at the fork, with `revision`, `depth`, and `[provide]` unchanged**
Run: `cat subprojects/frida-gum/subprojects/quickjs.wrap`
Expected:
```
[wrap-git]
url = https://github.com/OWNER/quickjs.git
revision = 080f16a095397ebcded3278385e33d39573afa0d
depth = 1

[provide]
dependency_names = quickjs
```

- [ ] **Step 7: Commit the wrap change inside the `frida-gum` submodule**
The wrap file lives inside the `frida-gum` submodule, which is its own git repository, so the commit is made there, not at the top-level `frida` repo.
```sh
cd subprojects/frida-gum
git add subprojects/quickjs.wrap
git commit -m "build: Point QuickJS wrap at owner fork"
cd -
```
Run: `git -C subprojects/frida-gum log -1 --oneline -- subprojects/quickjs.wrap`
Expected: one line of output ending in `build: Point QuickJS wrap at owner fork`.

- [ ] **Step 8: Fetch the submodules needed for the build**
```sh
python tools/ensure-submodules.py frida-core frida-python
```
Expected: command exits with code 0 and prints no error output.
Run: `ls subprojects/frida-core subprojects/frida-python`
Expected: both directory listings are non-empty.

- [ ] **Step 9: Configure the build with the Python bindings enabled**
```sh
./configure -Dfrida_python=enabled
```
Expected: command exits with code 0.
Run: `ls build/`
Expected: a non-empty listing, including `build.ninja`.

- [ ] **Step 10: Build**
```sh
make
```
Expected: command exits with code 0. This build fetches QuickJS from the fork per the updated wrap and builds `frida-gum`, `frida-core`, and `frida-python`.

- [ ] **Step 11: Confirm the QuickJS checkout used by the build is the pinned commit, fetched from the fork**
Run: `git -C subprojects/frida-gum/subprojects/quickjs rev-parse HEAD`
Expected: `080f16a095397ebcded3278385e33d39573afa0d`
Run: `git -C subprojects/frida-gum/subprojects/quickjs remote get-url origin`
Expected: `https://github.com/OWNER/quickjs.git`

- [ ] **Step 12: Create `tools/protect/README.md` documenting the build**
```sh
mkdir -p tools/protect
cat > tools/protect/README.md <<'EOF'
# Protect Tooling — Build Bring-up

This directory holds tooling for building and working with protected Frida agents.

## Custom Frida build

Frida's QuickJS dependency is pinned to a fork of the upstream Bellard QuickJS
fork used by Frida (`frida/quickjs`), so that protection tooling can rely on a
known, unmodified QuickJS baseline:

- Fork: `https://github.com/OWNER/quickjs.git` (replace `OWNER` with the fork owner)
- Pinned version: `2024-01-13`
- Pinned commit: `080f16a095397ebcded3278385e33d39573afa0d`
- Build options (set in `subprojects/frida-gum/meson.build`, do not change):
  `bignum=true` (CONFIG_BIGNUM), `libc=false`

The wrap file at `subprojects/frida-gum/subprojects/quickjs.wrap` points at the
fork above while keeping the pinned `revision`, `depth`, and `[provide]`
section unchanged. Because the wrap file lives inside the `frida-gum`
submodule, changes to it are committed inside that submodule, not at the
top-level `frida` repo.

## Building

Run these commands from the root of the `frida` repository:

```sh
python tools/ensure-submodules.py frida-core frida-python
./configure -Dfrida_python=enabled
make
```

Expected artifacts:

- `./build` is populated with the Meson build tree.
- The built `frida` Python module is usable from `./build` (consumed by later
  protection tooling).

## Verifying the QuickJS pin

```sh
grep -n 'url' subprojects/frida-gum/subprojects/quickjs.wrap
git -C subprojects/frida-gum/subprojects/quickjs rev-parse HEAD
```

The first command must show the fork URL above; the second must print
`080f16a095397ebcded3278385e33d39573afa0d`.
EOF
```

- [ ] **Step 13: Verify the README was created**
Run: `test -f tools/protect/README.md && echo OK`
Expected: `OK`

- [ ] **Step 14: Commit the README at the top-level `frida` repo**
```sh
git add tools/protect/README.md
git commit -m "docs: Document custom Frida build bring-up for protect tooling"
```
Run: `git log -1 --oneline -- tools/protect/README.md`
Expected: one line of output ending in `docs: Document custom Frida build bring-up for protect tooling`.
### T02: Bytecode Round-Trip Harness + Sample Agent

**Depends:** T01

**Files:**
- Create: `tools/harness/sample_agent.js`
- Create: `tools/harness/roundtrip.py`
- Test: `tools/harness/roundtrip.py`

**Interfaces:**
- Consumes: custom Frida build from T01
- Produces: `roundtrip.py` importable functions `compile(source_path: str) -> bytes` and `run(bytecode: bytes) -> str`, plus a CLI

**Constraints:** White-box desktop (Linux/Windows/macOS); custom Frida build required. QuickJS pinned (Bellard `2024-01-13`, bignum). Bytecode is QuickJS-only. Files in English. No secrets committed. Plain shell/editor/git only.

**Before running Step 2 or Step 4:** the custom Frida Python module built in T01 must be importable as `frida`. Point Python at it by setting `PYTHONPATH` to the built module's install location before running any command below, for example:
- Linux/macOS: `export PYTHONPATH=/path/to/frida-build/install/lib/python3.11/site-packages`
- Windows: `set PYTHONPATH=C:\path\to\frida-build\install\Lib\site-packages`

Replace the path with the actual install prefix produced by the T01 build. `python -c "import frida; print(frida.__file__)"` should print a path under that install location, not a pip-installed copy.

- [ ] **Step 1: Write the failing test**

Create `tools/harness/sample_agent.js`:
```js
send({ ok: true, marker: "ROUNDTRIP_OK", sum: 2 + 40 });
```

Create `tools/harness/roundtrip.py`:
```python
#!/usr/bin/env python3
"""Compile a JS agent to QuickJS bytecode, run the bytecode, and print the result.

Usage:
    python tools/harness/roundtrip.py <path-to-agent.js>

Exits 0 iff the agent's marker equals "ROUNDTRIP_OK".
"""
import sys


def compile(source_path: str) -> bytes:
    raise NotImplementedError


def run(bytecode: bytes) -> str:
    raise NotImplementedError


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: roundtrip.py <path-to-agent.js>", file=sys.stderr)
        return 2
    source_path = sys.argv[1]
    bytecode = compile(source_path)
    marker = run(bytecode)
    print(marker)
    return 0 if marker == "ROUNDTRIP_OK" else 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python tools/harness/roundtrip.py tools/harness/sample_agent.js`

Expected: FAIL — the process exits with a non-zero status and prints a traceback ending in `NotImplementedError` (raised by the `compile` stub).

- [ ] **Step 3: Write minimal implementation**

Replace the contents of `tools/harness/roundtrip.py` with:
```python
#!/usr/bin/env python3
"""Compile a JS agent to QuickJS bytecode, run the bytecode, and print the result.

Usage:
    python tools/harness/roundtrip.py <path-to-agent.js>

Exits 0 iff the agent's marker equals "ROUNDTRIP_OK".
"""
import json
import subprocess
import sys
import threading

import frida

MESSAGE_TIMEOUT_SECONDS = 30


def _spawn_dummy_process():
    if sys.platform == "win32":
        cmd = ["cmd", "/c", "timeout", "/t", "600"]
    else:
        cmd = [sys.executable, "-c", "import time;time.sleep(600)"]
    return subprocess.Popen(cmd)


def compile(source_path: str) -> bytes:
    with open(source_path, "r", encoding="utf-8") as f:
        source = f.read()
    device = frida.get_local_device()
    proc = _spawn_dummy_process()
    try:
        session = device.attach(proc.pid)
        try:
            return session.compile_script(source, name="agent")
        finally:
            session.detach()
    finally:
        proc.kill()
        proc.wait()


def run(bytecode: bytes) -> str:
    device = frida.get_local_device()
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
    finally:
        proc.kill()
        proc.wait()


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: roundtrip.py <path-to-agent.js>", file=sys.stderr)
        return 2
    source_path = sys.argv[1]
    bytecode = compile(source_path)
    marker = run(bytecode)
    print(marker)
    return 0 if marker == "ROUNDTRIP_OK" else 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python tools/harness/roundtrip.py tools/harness/sample_agent.js`

Expected: PASS — stdout prints exactly `ROUNDTRIP_OK` and the process exits with status 0.

- [ ] **Step 5: Commit**

```
git add tools/harness/sample_agent.js tools/harness/roundtrip.py
git commit -m "Add QuickJS bytecode round-trip harness and sample agent"
```
### T03: JS-source obfuscation step (L4) [P]

**Depends:** T02

**Files:**
- Create: `tools/protect/obfuscate.mjs`
- Create: `tools/protect/package.json`

**Interfaces:**
- Consumes: sample agent from T02
- Produces: CLI `node tools/protect/obfuscate.mjs <in.js> <out.js>` → obfuscated JS

**Constraints:** White-box desktop; custom Frida build required. Bytecode is QuickJS-only. Files in English. No secrets committed. Plain shell/editor/git only.

**Context:** The agent obfuscated here runs inside Frida's QuickJS runtime, not Node or a browser. Frida injects globals such as `Interceptor`, `Module`, `Memory`, `Process`, `Thread`, `NativePointer`, `ptr`, `send`, `recv`, `rpc`, `Script`, and `console` into the agent as free identifiers. The obfuscator must never rename globals, or every call into these Frida APIs breaks. Only local identifiers may be renamed.

- [ ] **Step 1: Write the failing test**

Create `tools/protect/test.sh`:

```sh
#!/bin/sh
set -e

OUT=/tmp/obfuscated_sample_agent.js

node tools/protect/obfuscate.mjs tools/harness/sample_agent.js "$OUT"

node --check "$OUT"

count=$(grep -c ROUNDTRIP_OK "$OUT" || true)
if [ "$count" != "0" ]; then
  echo "FAIL: ROUNDTRIP_OK still present ($count occurrences) in $OUT"
  exit 1
fi

echo "PASS"
```

- [ ] **Step 2: Run test to verify it fails**

Run (from the repository root):
```
sh tools/protect/test.sh
```
Expected: FAIL — node reports it cannot find the `obfuscate.mjs` module (e.g. `Error: Cannot find module '.../tools/protect/obfuscate.mjs'`), and the script exits with a non-zero status before printing `PASS`.

- [ ] **Step 3: Write minimal implementation**

Create `tools/protect/package.json`:

```json
{
  "name": "frida-agent-protect",
  "version": "1.0.0",
  "private": true,
  "type": "module",
  "description": "JS-source obfuscation step for hardening the Frida agent bundle before packaging.",
  "dependencies": {
    "javascript-obfuscator": "4.1.1"
  }
}
```

Create `tools/protect/obfuscate.mjs`:

```js
import { readFileSync, writeFileSync } from 'node:fs';
import JavaScriptObfuscator from 'javascript-obfuscator';

const [, , inputPath, outputPath] = process.argv;

if (!inputPath || !outputPath) {
  console.error('Usage: node obfuscate.mjs <in.js> <out.js>');
  process.exit(1);
}

const source = readFileSync(inputPath, 'utf8');

const result = JavaScriptObfuscator.obfuscate(source, {
  compact: true,
  identifierNamesGenerator: 'hexadecimal',
  renameGlobals: false,
  stringArray: true,
  stringArrayThreshold: 1,
  stringArrayEncoding: ['rc4'],
  numbersToExpressions: true,
  simplify: true,
  controlFlowFlattening: false
});

writeFileSync(outputPath, result.getObfuscatedCode(), 'utf8');
console.log(`Obfuscated ${inputPath} -> ${outputPath}`);
```

Install the pinned dependency (from the repository root):
```
cd tools/protect && npm install && cd -
```
This creates `tools/protect/node_modules/` and `tools/protect/package-lock.json`. Run `npm install` in `tools/protect/` whenever this package is set up on a fresh checkout, since `node_modules/` is not committed.

- [ ] **Step 4: Run test to verify it passes**

Run (from the repository root):
```
sh tools/protect/test.sh
```
Expected: PASS — the script prints `PASS` and exits with status 0.

- [ ] **Step 5: Commit**

```
git add tools/protect/package.json tools/protect/package-lock.json tools/protect/obfuscate.mjs tools/protect/test.sh
git commit -m "Add JS-source obfuscation CLI (L4)"
```
### T04: Blob leak-scan tool + Phase-1a gate (L4)

**Depends:** T03

**Files:**
- Create: `tools/protect/scan_blob.py`
- Create: `tools/protect/test_scan_blob.py`

**Interfaces:**
- Consumes: `obfuscate.mjs` (T03), `roundtrip.compile` (T02)
- Produces: CLI `python tools/protect/scan_blob.py <blob> --forbid <token>...` exits 1 if any forbidden token appears in the blob.

**Constraints:**
- White-box desktop; custom Frida build required.
- Bytecode is QuickJS-only.
- Files in English.
- No secrets committed.
- Plain shell/editor/git only.

- [ ] **Step 1: Write the failing test**

Create `tools/protect/test_scan_blob.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 tools/protect/test_scan_blob.py`

Expected: FAIL. `tools/protect/scan_blob.py` does not exist yet, so the subprocess call fails to launch the script and returns a non-zero exit code that is not `1`, e.g.:
```
AssertionError: expected exit 1, got 2: stdout='' stderr="python3: can't open file '.../tools/protect/scan_blob.py': [Errno 2] No such file or directory\n"
```

- [ ] **Step 3: Write minimal implementation**

Create `tools/protect/scan_blob.py`:

```python
import argparse
import sys


def find_leaked_tokens(blob, tokens):
    leaked = []
    for token in tokens:
        utf8_bytes = token.encode("utf-8")
        utf16le_bytes = token.encode("utf-16-le")
        if utf8_bytes in blob or utf16le_bytes in blob:
            leaked.append(token)
    return leaked


def main():
    parser = argparse.ArgumentParser(
        description="Scan a QuickJS bytecode blob for forbidden tokens."
    )
    parser.add_argument("blob", help="Path to the bytecode blob file")
    parser.add_argument(
        "--forbid",
        nargs="+",
        required=True,
        help="Tokens that must not appear in the blob, as UTF-8 or UTF-16LE bytes",
    )
    args = parser.parse_args()

    with open(args.blob, "rb") as f:
        blob = f.read()

    leaked = find_leaked_tokens(blob, args.forbid)

    if leaked:
        for token in leaked:
            print(f"LEAKED: {token}")
        sys.exit(1)

    print("CLEAN: no forbidden tokens found")
    sys.exit(0)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 tools/protect/test_scan_blob.py`

Expected: PASS. Output is:
```
ALL TESTS PASSED
```

- [ ] **Step 5: Find a local identifier in the sample agent to use in the gate demonstration**

Run:
```bash
LOCAL_NAME=$(grep -oE 'let [A-Za-z_][A-Za-z0-9_]*' tools/harness/sample_agent.js | head -1 | awk '{print $2}')
echo "LOCAL_NAME=$LOCAL_NAME"
```

Expected: prints a non-empty identifier name, e.g. `LOCAL_NAME=someVariable`. If the output is empty, open `tools/harness/sample_agent.js`, find a variable declared with `let` or `const` inside a function body, and set `LOCAL_NAME` to that name manually instead (`LOCAL_NAME=<name found in file>`).

- [ ] **Step 6: Obfuscate the sample agent**

Run: `node tools/protect/obfuscate.mjs tools/harness/sample_agent.js /tmp/agent.obf.js`

Expected: command exits 0 and `/tmp/agent.obf.js` is created.

- [ ] **Step 7: Compile the obfuscated agent to a bytecode blob**

Run:
```bash
python3 - <<'PY'
import sys
sys.path.insert(0, "tools/protect")
from roundtrip import compile as rt_compile

blob = rt_compile("/tmp/agent.obf.js")
open("/tmp/agent.obf.blob", "wb").write(blob)
PY
```

Expected: command exits 0 and `/tmp/agent.obf.blob` is created. If it fails with `ModuleNotFoundError: No module named 'roundtrip'`, adjust the `sys.path.insert` line above to point at the directory that actually holds `roundtrip.py` in your working tree, then re-run.

- [ ] **Step 8: Positive gate check — obfuscated blob is clean**

Run: `python tools/protect/scan_blob.py /tmp/agent.obf.blob --forbid "$LOCAL_NAME" ROUNDTRIP_OK`

Expected: exit code 0, output:
```
CLEAN: no forbidden tokens found
```
This confirms the obfuscated blob no longer contains the original local identifier or the `ROUNDTRIP_OK` literal.

- [ ] **Step 9: Compile the plain (non-obfuscated) agent to a bytecode blob**

Run:
```bash
python3 - <<'PY'
import sys
sys.path.insert(0, "tools/protect")
from roundtrip import compile as rt_compile

blob = rt_compile("tools/harness/sample_agent.js")
open("/tmp/agent.plain.blob", "wb").write(blob)
PY
```

Expected: command exits 0 and `/tmp/agent.plain.blob` is created.

- [ ] **Step 10: Negative gate check — plain blob leaks**

Run: `python tools/protect/scan_blob.py /tmp/agent.plain.blob --forbid ROUNDTRIP_OK`

Expected: exit code 1, output:
```
LEAKED: ROUNDTRIP_OK
```
This confirms the scanner correctly flags the un-obfuscated blob, proving both the scanner and the obfuscation from Step 6-8 work.

- [ ] **Step 11: Commit**

```bash
git add tools/protect/scan_blob.py tools/protect/test_scan_blob.py
git commit -m "Add blob leak-scan tool (T04)"
```
### T05: QuickJS opcode permutation in the fork (L3) [P]

**Depends:** T01

**Files:**
- Create: `tools/protect/opcode_permute.py`
- Modify: `<fork checkout>/quickjs-opcode.h` (the fork set up by T01; exact path located in Step 2)

**Interfaces:**
- Consumes: fork from T01.
- Produces: `python tools/protect/opcode_permute.py --seed <hex> --quickjs <path>` deterministically rewrites the `DEF(...)` ordering (safe subset only); yields a permuted custom build.

- [ ] **Step 1: Create the tool directory and git-ignore the seed file**
```
mkdir -p tools/protect
grep -qxF 'tools/protect/.seed' .gitignore || echo 'tools/protect/.seed' >> .gitignore
```

- [ ] **Step 2: Locate the fork's `quickjs-opcode.h` and `quickjs.c`**
Run from the repo root:
```
find . -name 'quickjs-opcode.h' -not -path '*/build/*' -not -path '*/node_modules/*'
```
Expected: exactly one path printed, inside the fork checkout that T01 set up. If more than one path is printed, pick the one under the fork checkout (not a `build/` output directory). Every later command that references `$QUICKJS_DIR` means "the directory containing that `quickjs-opcode.h`". Confirm `quickjs.c` sits next to it:
```
ls "$QUICKJS_DIR/quickjs.c"
```
Expected: the file exists (no "No such file" error).

- [ ] **Step 3: Grep for opcodes used with arithmetic offsets**
```
cd "$QUICKJS_DIR" && grep -nE 'OP_[a-z0-9_]+ *[-+]' quickjs.c
```
Expected: one or more matches, e.g. lines using `OP_get_loc0 + n`-style expressions. Write down every distinct `OP_<name>` identifier in the output — these opcodes are addressed by arithmetic offset and must never move.

- [ ] **Step 4: Grep for opcodes used in range comparisons, and check for a short-opcodes region**
```
cd "$QUICKJS_DIR" && grep -nE '(>=|<=|<|>) *OP_' quickjs.c
grep -n 'SHORT_OPCODES' quickjs-opcode.h
```
Expected: the first command prints one or more matches; write down every distinct `OP_<name>` identifier used in a `<`, `<=`, `>`, `>=` comparison. The second command shows whether `quickjs-opcode.h` has a `#ifdef SHORT_OPCODES` guarded region — if it does, every `DEF(...)` line inside that guarded block is part of the constrained set too (Step 9 handles this structurally, by position, so those names don't need to be listed by hand).

- [ ] **Step 5: Write the script skeleton with a failing self-test**
Create `tools/protect/opcode_permute.py`:
```python
#!/usr/bin/env python3
"""Deterministically permute the safe subset of QuickJS DEF(...) opcode
ordering in the fork's quickjs-opcode.h. Opcodes reached via arithmetic
offset or range comparison in quickjs.c (see CONSTRAINED_OPCODES) keep
their original slot; only the remaining opcodes are shuffled."""
import argparse
import random
import re
import shutil
from pathlib import Path

DEF_RE = re.compile(r'^\s*DEF\(\s*([A-Za-z0-9_]+)\s*,')

# Bare DEF(...) identifiers (no "OP_" prefix) that quickjs.c reaches by
# arithmetic offset or range comparison against the OP_* enum. Found via
# `grep -nE 'OP_[a-z0-9_]+ *[-+]' quickjs.c` and
# `grep -nE '(>=|<=|<|>) *OP_' quickjs.c` in the fork checkout (Steps 3-4).
# Extend this set with anything the grep output found that isn't listed
# here yet, e.g. any OP_TEMP_* family.
CONSTRAINED_OPCODES = {
    "get_loc0", "get_loc1", "get_loc2", "get_loc3",
    "put_loc0", "put_loc1", "put_loc2", "put_loc3",
    "get_arg0", "get_arg1", "get_arg2", "get_arg3",
    "push_i32",
}


def replace_def_id(line, new_id):
    m = DEF_RE.match(line)
    start, end = m.span(1)
    return line[:start] + new_id + line[end:]


def parse_def_lines(text):
    """Return (lines, defs) where defs is [(line_index, opcode_id), ...]
    for every DEF(...) line, in file order."""
    lines = text.splitlines(keepends=True)
    defs = [(i, DEF_RE.match(l).group(1)) for i, l in enumerate(lines) if DEF_RE.match(l)]
    return lines, defs


def find_short_opcode_start(lines):
    for i, line in enumerate(lines):
        if line.strip().startswith('#ifdef') and 'SHORT_OPCODES' in line:
            return i
    return None


def generate_permutation(opcode_ids, seed_hex, constrained):
    """Return a reordering of opcode_ids: ids in `constrained` keep their
    original slot; the rest are shuffled deterministically from seed_hex."""
    raise NotImplementedError


def self_test():
    ids = ["a", "get_loc0", "b", "c", "get_arg1", "d", "e"]
    constrained = {"get_loc0", "get_arg1"}
    permuted = generate_permutation(ids, "deadbeef", constrained)
    assert sorted(permuted) == sorted(ids), "not a bijection"
    assert permuted[1] == "get_loc0", "constrained opcode moved"
    assert permuted[4] == "get_arg1", "constrained opcode moved"
    assert permuted == generate_permutation(ids, "deadbeef", constrained), "not deterministic for same seed"
    assert permuted != generate_permutation(ids, "cafef00d", constrained), "seed had no effect"
    print("self-test OK")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", help="hex seed, e.g. output of secrets.token_hex(16)")
    parser.add_argument("--quickjs", help="path to the fork's quickjs source directory")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        return

    if not args.seed or not args.quickjs:
        parser.error("--seed and --quickjs are required unless --self-test is given")

    raise NotImplementedError


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Run the self-test and confirm it fails**
Run: `python3 tools/protect/opcode_permute.py --self-test`
Expected: a traceback ending with `NotImplementedError`, raised from `generate_permutation` (it isn't implemented yet).

- [ ] **Step 7: Implement `generate_permutation`**
Replace the `raise NotImplementedError` body of `generate_permutation` in `tools/protect/opcode_permute.py` with:
```python
    rng = random.Random(int(seed_hex, 16))
    safe_slots = [i for i, oid in enumerate(opcode_ids) if oid not in constrained]
    shuffled = [opcode_ids[i] for i in safe_slots]
    rng.shuffle(shuffled)
    result = list(opcode_ids)
    for slot, oid in zip(safe_slots, shuffled):
        result[slot] = oid
    return result
```

- [ ] **Step 8: Run the self-test and confirm it passes**
Run: `python3 tools/protect/opcode_permute.py --self-test`
Expected output: `self-test OK`

- [ ] **Step 9: Implement the file-rewrite path**
Replace the `raise NotImplementedError` at the bottom of `main()` with:
```python
    apply_permutation(args.quickjs, args.seed)
```
Add `apply_permutation` above `main()`:
```python
def apply_permutation(quickjs_dir, seed_hex):
    quickjs_dir = Path(quickjs_dir)
    header = quickjs_dir / "quickjs-opcode.h"
    canonical = quickjs_dir / "quickjs-opcode.h.canonical"
    if not canonical.exists():
        shutil.copyfile(header, canonical)
    lines, defs = parse_def_lines(canonical.read_text())
    short_start = find_short_opcode_start(lines)
    constrained = set(CONSTRAINED_OPCODES)
    if short_start is not None:
        constrained |= {oid for idx, oid in defs if idx > short_start}
    ids = [oid for _, oid in defs]
    new_ids = generate_permutation(ids, seed_hex, constrained)
    for (idx, _old_id), new_id in zip(defs, new_ids):
        lines[idx] = replace_def_id(lines[idx], new_id)
    header.write_text("".join(lines))
    moved = sum(1 for old, new in zip(ids, new_ids) if old != new)
    print(f"permuted {len(defs)} opcodes, {moved} moved, {len(constrained)} held fixed -> {header}")
```
This always regenerates from the saved `.canonical` copy (written once, on first run), so re-running the script — even with a different seed — never permutes an already-permuted file.

- [ ] **Step 10: Add any extra constrained names found by the grep review**
Reopen `tools/protect/opcode_permute.py` and, from what was written down in Steps 3-4, add any `OP_<name>` identifier not already in `CONSTRAINED_OPCODES` (strip the `OP_` prefix to match the `DEF(...)` bare-name form, e.g. `OP_temp_foo` becomes `"temp_foo"`).

- [ ] **Step 11: Generate the per-build seed**
```
python3 -c "import secrets;print(secrets.token_hex(16))" > tools/protect/.seed
cat tools/protect/.seed
```
Expected: a 32-character hex string is printed and saved. This file is git-ignored (Step 1) and must never be committed.

- [ ] **Step 12: Apply the permutation to the fork**
```
python3 tools/protect/opcode_permute.py --seed "$(cat tools/protect/.seed)" --quickjs "$QUICKJS_DIR"
```
Expected: a line like `permuted N opcodes, M moved, K held fixed -> .../quickjs-opcode.h`, and `$QUICKJS_DIR/quickjs-opcode.h.canonical` now exists alongside the rewritten `quickjs-opcode.h`.

- [ ] **Step 13: Verify the rewrite is a bijection**
```
diff <(grep -oE 'DEF\([A-Za-z0-9_]+' "$QUICKJS_DIR/quickjs-opcode.h.canonical" | sort) \
     <(grep -oE 'DEF\([A-Za-z0-9_]+' "$QUICKJS_DIR/quickjs-opcode.h" | sort)
```
Expected: no output — both files define exactly the same set of opcode names, just reordered.

- [ ] **Step 14: Verify constrained opcodes did not move**
```
for op in get_loc0 get_loc1 get_loc2 get_loc3 put_loc0 put_loc1 put_loc2 put_loc3 get_arg0 get_arg1 get_arg2 get_arg3 push_i32; do
  a=$(grep -n "DEF($op," "$QUICKJS_DIR/quickjs-opcode.h.canonical" | cut -d: -f1)
  b=$(grep -n "DEF($op," "$QUICKJS_DIR/quickjs-opcode.h" | cut -d: -f1)
  [ "$a" = "$b" ] || echo "MOVED: $op ($a -> $b)"
done
```
Expected: no output. If any line prints `MOVED: ...`, that opcode leaked into the shuffle — go back to Step 10, add it to `CONSTRAINED_OPCODES`, restore `$QUICKJS_DIR/quickjs-opcode.h` from `$QUICKJS_DIR/quickjs-opcode.h.canonical`, delete the `.canonical` file, and redo Steps 12-14.

- [ ] **Step 15: Rebuild the custom Frida**
```
make
```
Expected: the build completes with no errors.

- [ ] **Step 16: HARD correctness gate — the T02 round-trip harness must still pass**
```
python tools/harness/roundtrip.py tools/harness/sample_agent.js
echo "exit code: $?"
```
Expected: stdout contains `ROUNDTRIP_OK` and `exit code: 0`. If it fails, the permutation touched a constrained opcode that Steps 3-4/10 missed — re-check the grep output (or bisect by moving suspect opcodes into `CONSTRAINED_OPCODES` one at a time), restore `quickjs-opcode.h` from `quickjs-opcode.h.canonical`, delete the `.canonical` file, and redo Steps 10-16.

- [ ] **Step 17: Commit**
```
git add tools/protect/opcode_permute.py .gitignore
git commit -m "protect: add QuickJS opcode permutation tool for the fork"
```
`tools/protect/.seed` and the rewritten `quickjs-opcode.h` in the fork checkout are build artifacts of this custom build and are not committed.
### T06: Stock-disassembler-fails validation (L3 gate)

**Depends:** T05, T02

**Files:**
- Create: `tools/protect/stock_reader.c`
- Create: `tools/protect/verify_disasm.sh`

**Interfaces:**
- Consumes: permuted build (T05), roundtrip (T02)
- Produces: a script that asserts a stock QuickJS reader FAILS/mis-decodes the permuted blob while the custom Frida runs it correctly

**Constraints:** White-box desktop; custom Frida build required. QuickJS pinned Bellard `2024-01-13` bignum. Files in English. No secrets committed. Plain shell/editor/git only.

This task builds a minimal reader linked against **stock**, unmodified QuickJS and proves it
cannot make sense of a GumJS bytecode blob that has been through the T05 opcode permutation,
while the custom Frida build still runs that same blob correctly. A control run proves the
stock reader itself works on ordinary, non-permuted bytecode, so a failure on the permuted blob
can only be explained by the permutation.

- [ ] **Step 1: Clone stock QuickJS at the pinned commit**

Run:
```
git clone https://github.com/bellard/quickjs.git /tmp/stock-quickjs
cd /tmp/stock-quickjs
git checkout 3f81070e573e3592728dbbbd04c84c498b20d6dc
```
Expected: the `git checkout` line prints `HEAD is now at 3f81070e ...` (a short form of the pinned
commit hash) with no error output.

- [ ] **Step 2: Build the stock QuickJS bignum library**

Run:
```
cd /tmp/stock-quickjs
make libquickjs.bignum.a
```
Expected: the build runs to completion with no error lines, ending with an `ar rcs
libquickjs.bignum.a ...` step, and the file `/tmp/stock-quickjs/libquickjs.bignum.a` exists
afterward (check with `ls -l libquickjs.bignum.a`).

- [ ] **Step 3: Write the stock reader**

Save the following as `tools/protect/stock_reader.c` in the frida repository:
```c
/*
 * stock_reader.c — minimal stock QuickJS bytecode reader.
 *
 * Usage:
 *   stock_reader <bytecode-file>
 *       Reads <bytecode-file> with the stock JS_ReadObject() and prints
 *       PARSED_OK on success or PARSE_FAIL plus the exception on error.
 *
 *   stock_reader --make-control <script.js> <out.bin>
 *       Compiles <script.js> with the stock engine and writes the
 *       resulting serialized bytecode to <out.bin>. Used only to produce
 *       a non-permuted control blob for the reader sanity check.
 */
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include "quickjs.h"

static uint8_t *read_file(const char *path, size_t *out_len) {
    FILE *f = fopen(path, "rb");
    if (!f) return NULL;
    fseek(f, 0, SEEK_END);
    long len = ftell(f);
    fseek(f, 0, SEEK_SET);
    uint8_t *buf = malloc((size_t)len);
    if (!buf || fread(buf, 1, (size_t)len, f) != (size_t)len) {
        fclose(f);
        free(buf);
        return NULL;
    }
    fclose(f);
    *out_len = (size_t)len;
    return buf;
}

static int make_control(const char *script_path, const char *out_path) {
    size_t src_len;
    uint8_t *src = read_file(script_path, &src_len);
    if (!src) {
        fprintf(stderr, "PARSE_FAIL: cannot read %s\n", script_path);
        return 1;
    }

    JSRuntime *rt = JS_NewRuntime();
    JSContext *ctx = JS_NewContext(rt);

    JSValue obj = JS_Eval(ctx, (const char *)src, src_len, script_path,
                          JS_EVAL_TYPE_GLOBAL | JS_EVAL_FLAG_COMPILE_ONLY);
    free(src);
    if (JS_IsException(obj)) {
        JSValue exc = JS_GetException(ctx);
        const char *msg = JS_ToCString(ctx, exc);
        fprintf(stderr, "PARSE_FAIL: %s\n", msg ? msg : "(no exception message)");
        JS_FreeCString(ctx, msg);
        JS_FreeValue(ctx, exc);
        JS_FreeValue(ctx, obj);
        JS_FreeContext(ctx);
        JS_FreeRuntime(rt);
        return 1;
    }

    size_t bc_len;
    uint8_t *bc = JS_WriteObject(ctx, &bc_len, obj, JS_WRITE_OBJ_BYTECODE);
    JS_FreeValue(ctx, obj);
    if (!bc) {
        fprintf(stderr, "PARSE_FAIL: JS_WriteObject failed\n");
        JS_FreeContext(ctx);
        JS_FreeRuntime(rt);
        return 1;
    }

    FILE *out = fopen(out_path, "wb");
    if (!out || fwrite(bc, 1, bc_len, out) != bc_len) {
        fprintf(stderr, "PARSE_FAIL: cannot write %s\n", out_path);
        if (out) fclose(out);
        js_free(ctx, bc);
        JS_FreeContext(ctx);
        JS_FreeRuntime(rt);
        return 1;
    }
    fclose(out);
    js_free(ctx, bc);
    JS_FreeContext(ctx);
    JS_FreeRuntime(rt);
    printf("CONTROL_WRITTEN\n");
    return 0;
}

static int read_bytecode(const char *bc_path) {
    size_t len;
    uint8_t *buf = read_file(bc_path, &len);
    if (!buf) {
        printf("PARSE_FAIL: cannot open %s\n", bc_path);
        return 1;
    }

    JSRuntime *rt = JS_NewRuntime();
    JSContext *ctx = JS_NewContext(rt);

    JSValue obj = JS_ReadObject(ctx, buf, len, JS_READ_OBJ_BYTECODE);
    free(buf);

    if (JS_IsException(obj)) {
        JSValue exc = JS_GetException(ctx);
        const char *msg = JS_ToCString(ctx, exc);
        printf("PARSE_FAIL: %s\n", msg ? msg : "(no exception message)");
        JS_FreeCString(ctx, msg);
        JS_FreeValue(ctx, exc);
        JS_FreeValue(ctx, obj);
        JS_FreeContext(ctx);
        JS_FreeRuntime(rt);
        return 1;
    }

    printf("PARSED_OK\n");
    JS_FreeValue(ctx, obj);
    JS_FreeContext(ctx);
    JS_FreeRuntime(rt);
    return 0;
}

int main(int argc, char **argv) {
    if (argc == 4 && strcmp(argv[1], "--make-control") == 0) {
        return make_control(argv[2], argv[3]);
    }
    if (argc == 2) {
        return read_bytecode(argv[1]);
    }
    fprintf(stderr, "usage: %s <bytecode-file>\n", argv[0]);
    fprintf(stderr, "       %s --make-control <script.js> <out.bin>\n", argv[0]);
    return 2;
}
```

- [ ] **Step 4: Compile the stock reader against the stock QuickJS library**

On Linux, run:
```
cc -DCONFIG_BIGNUM -I/tmp/stock-quickjs -o /tmp/stock-quickjs/stock_reader \
  tools/protect/stock_reader.c /tmp/stock-quickjs/libquickjs.bignum.a -lm -lpthread -ldl
```
Expected: the command exits with no error output and the executable file
`/tmp/stock-quickjs/stock_reader` exists afterward (check with `ls -l /tmp/stock-quickjs/stock_reader`).

On macOS, use `clang` in place of `cc` and drop `-ldl` (not present on macOS):
```
clang -DCONFIG_BIGNUM -I/tmp/stock-quickjs -o /tmp/stock-quickjs/stock_reader \
  tools/protect/stock_reader.c /tmp/stock-quickjs/libquickjs.bignum.a -lm -lpthread
```

On Windows, run the clone and `make libquickjs.bignum.a` steps inside a MinGW-w64/MSYS2 shell
(the upstream QuickJS Makefile targets POSIX toolchains), then compile with `gcc`:
```
gcc -DCONFIG_BIGNUM -I/tmp/stock-quickjs -o stock_reader.exe \
  tools/protect/stock_reader.c /tmp/stock-quickjs/libquickjs.bignum.a -lm
```
With MSVC, build the library through the MinGW/MSYS2 step above (MSVC cannot build the upstream
Makefile directly), then compile only the reader against the resulting archive:
```
cl /DCONFIG_BIGNUM /I\tmp\stock-quickjs stock_reader.c /link libquickjs.bignum.a
```

- [ ] **Step 5: Prove the reader is correct — control run on a non-permuted blob**

Run:
```
echo "1 + 1;" > /tmp/control.js
/tmp/stock-quickjs/stock_reader --make-control /tmp/control.js /tmp/control.bin
```
Expected stdout:
```
CONTROL_WRITTEN
```

Run:
```
/tmp/stock-quickjs/stock_reader /tmp/control.bin
```
Expected stdout:
```
PARSED_OK
```
This confirms the stock reader correctly parses ordinary, non-permuted QuickJS bytecode before
it is ever pointed at a permuted blob.

- [ ] **Step 6: Write the verification script**

Save the following as `tools/protect/verify_disasm.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail

# roundtrip is the T02 tool with "compile" and "run" subcommands; override
# ROUNDTRIP if it lives at a different path in your checkout.
ROUNDTRIP="${ROUNDTRIP:-tools/protect/roundtrip.sh}"
# stock_reader is the binary built in Step 4; override STOCK_READER if you
# placed it somewhere other than /tmp/stock-quickjs/stock_reader.
STOCK_READER="${STOCK_READER:-/tmp/stock-quickjs/stock_reader}"
# SAMPLE_AGENT is the JS fixture roundtrip.compile takes as input; override
# it to match the fixture your roundtrip tool from T02 expects.
SAMPLE_AGENT="${SAMPLE_AGENT:-tools/protect/sample-agent.js}"

TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT

PERMUTED_BLOB="$TMP_DIR/permuted.bin"
CONTROL_SCRIPT="$TMP_DIR/control.js"
CONTROL_BLOB="$TMP_DIR/control.bin"

echo "== L3 gate: stock disassembler must fail on the permuted blob =="

echo "[1/4] Compiling sample agent to a permuted blob..."
"$ROUNDTRIP" compile "$SAMPLE_AGENT" "$PERMUTED_BLOB"

echo "[2/4] Running stock reader on the permuted blob (expect PARSE_FAIL)..."
STOCK_OUT=$("$STOCK_READER" "$PERMUTED_BLOB" || true)
echo "$STOCK_OUT"
if echo "$STOCK_OUT" | grep -q "^PARSED_OK$"; then
    echo "GATE FAILED: stock reader parsed the permuted blob (PARSED_OK) -- permutation is not effective."
    exit 1
fi

echo "[3/4] Running the SAME blob under the custom Frida (expect ROUNDTRIP_OK)..."
ROUNDTRIP_OUT=$("$ROUNDTRIP" run "$PERMUTED_BLOB")
echo "$ROUNDTRIP_OUT"
if ! echo "$ROUNDTRIP_OUT" | grep -q "^ROUNDTRIP_OK$"; then
    echo "GATE FAILED: custom Frida did not run the permuted blob correctly."
    exit 1
fi

echo "[4/4] Control: stock reader must parse a NON-permuted blob..."
echo "1 + 1;" > "$CONTROL_SCRIPT"
"$STOCK_READER" --make-control "$CONTROL_SCRIPT" "$CONTROL_BLOB"
CONTROL_OUT=$("$STOCK_READER" "$CONTROL_BLOB")
echo "$CONTROL_OUT"
if ! echo "$CONTROL_OUT" | grep -q "^PARSED_OK$"; then
    echo "GATE FAILED: stock reader could not even parse a non-permuted control blob -- reader itself is broken."
    exit 1
fi

echo "L3 GATE PASSED: stock reader fails on the permuted blob, custom Frida runs it, control blob parses cleanly."
```

- [ ] **Step 7: Make the script executable**

Run:
```
chmod +x tools/protect/verify_disasm.sh
```
Expected: no output; `ls -l tools/protect/verify_disasm.sh` shows the executable (`x`) permission
bit set for the owner.

- [ ] **Step 8: Run the L3 gate against the permuted build**

From the repository root, with the T05-permuted custom Frida build and the T02 `roundtrip` tool
both in place, run:
```
STOCK_READER=/tmp/stock-quickjs/stock_reader ./tools/protect/verify_disasm.sh
echo "exit status: $?"
```
Expected stdout ends with:
```
L3 GATE PASSED: stock reader fails on the permuted blob, custom Frida runs it, control blob parses cleanly.
exit status: 0
```
The `[2/4]` line must show `PARSE_FAIL: ...` (or otherwise anything other than the exact line
`PARSED_OK`) for the permuted blob, the `[3/4]` line must show `ROUNDTRIP_OK`, and the `[4/4]`
line must show `PARSED_OK` for the control blob. If `[2/4]` prints `PARSED_OK`, the script prints
`GATE FAILED: stock reader parsed the permuted blob ...` and exits with status 1 — the permutation
from T05 is not effective and must be fixed before this task can pass.

- [ ] **Step 9: Commit**

Run:
```
git add tools/protect/stock_reader.c tools/protect/verify_disasm.sh
git commit -m "protect: add L3 gate asserting stock QuickJS fails on permuted bytecode"
```
Expected: the commit succeeds; `git log -1 --stat` lists both `tools/protect/stock_reader.c` and
`tools/protect/verify_disasm.sh` as added files.
### T07: AEAD bytecode encryption + build orchestrator (L3) [P]

**Depends:** T02

**Files:**
- Create: `tools/protect/encrypt_blob.py`
- Create: `tools/protect/build_protected.py`

**Interfaces:**
- Consumes: `obfuscate.mjs` (T03), `roundtrip.compile` (T02)
- Produces: container `MAGIC(4)='FPB1' || nonce(12) || AES-256-GCM ciphertext(+tag)`; `encrypt_blob(plain: bytes, key: bytes) -> bytes`; `build_protected.py <agent.js> <out.fpb>` = obfuscate→compile→encrypt

Context: this is a white-box desktop build that requires a custom Frida build. The AES-256 key is 32 bytes, unique per build, and is read from a git-ignored key file — never hard-code it and never commit it. Use only plain shell, an editor, and git for these steps.

- [ ] **Step 1: Write the failing test**

This test needs the `cryptography` package. Install it first:

```
pip install cryptography
```

Create `tools/protect/test_encrypt_blob.py`:

```python
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from encrypt_blob import encrypt_blob, decrypt_blob


def test_round_trip():
    key = os.urandom(32)
    plain = b"hello"
    container = encrypt_blob(plain, key)
    assert container[:4] == b"FPB1"
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


if __name__ == "__main__":
    test_round_trip()
    test_wrong_key_raises()
    print("OK")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 tools/protect/test_encrypt_blob.py`

Expected: FAIL with `ModuleNotFoundError: No module named 'encrypt_blob'` (the file does not exist yet).

- [ ] **Step 3: Write minimal implementation**

Create `tools/protect/encrypt_blob.py`:

```python
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
    if container[:4] != MAGIC:
        raise ValueError("bad magic: not an FPB1 container")
    nonce = container[4:4 + NONCE_LEN]
    ciphertext = container[4 + NONCE_LEN:]
    return AESGCM(key).decrypt(nonce, ciphertext, None)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 tools/protect/test_encrypt_blob.py`

Expected: PASS, prints `OK`.

- [ ] **Step 5: Write the failing orchestrator test**

Create `tools/protect/test_build_protected.py`:

```python
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


if __name__ == "__main__":
    test_build_protected_produces_fpb()
    print("OK")
```

- [ ] **Step 6: Run test to verify it fails**

Run: `python3 tools/protect/test_build_protected.py`

Expected: FAIL — the subprocess returns a non-zero exit code because `tools/protect/build_protected.py` does not exist yet.

- [ ] **Step 7: Write minimal implementation**

Create `tools/protect/build_protected.py`:

```python
#!/usr/bin/env python3
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(__file__))

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
```

- [ ] **Step 8: Run test to verify it passes**

Run: `python3 tools/protect/test_build_protected.py`

Expected: PASS, prints `OK`. (This step requires `tools/protect/obfuscate.mjs` from T03 and the `roundtrip` module's `compile` function from T02 to already be present in the tree; if either is missing, finish landing those first, then re-run this command.)

- [ ] **Step 9: Generate a local key, update `.gitignore`, and commit**

Generate a per-build key (never commit this file):

```
python -c "import os;open('tools/protect/.key','wb').write(os.urandom(32))"
```

Add the key and seed files to `.gitignore`:

```
cat >> .gitignore <<'EOF'
tools/protect/.key
tools/protect/.seed
EOF
```

Stage and commit only the source files and the `.gitignore` update — never the key itself:

```
git add tools/protect/encrypt_blob.py tools/protect/build_protected.py tools/protect/test_encrypt_blob.py tools/protect/test_build_protected.py .gitignore
git commit -m "protect: add AEAD bytecode encryption and build orchestrator"
```
### T08: GumJS decrypt-before-read hook + Phase-1b e2e gate (L3)

**Depends:** T07, T01

**Files:**
- Create: `subprojects/frida-gum/lib/prot/gumprotaesgcm.h`
- Create: `subprojects/frida-gum/lib/prot/gumprotaesgcm.c`
- Create: `subprojects/frida-gum/lib/prot/.gitignore` (ignores the generated `gumprotkey.h`)
- Modify: `subprojects/frida-gum/bindings/gumjs/gumquickscriptbackend.c` — `gum_quick_script_backend_read_program()` (the `JS_ReadObject` call at line 659) and `gum_compile_module()` (the magic-byte check at lines 617-626)
- Modify: `subprojects/frida-gum/bindings/gumjs/meson.build` — add the two new source files to `gumjs_sources`

**Interfaces:**
- Consumes: container format + key from T07 — `b'FPB1'` + 12-byte nonce + AES-256-GCM ciphertext(+16-byte tag).
- Produces: `static GBytes * gum_prot_decrypt (const guint8 * data, gsize size)`; `gboolean gum_prot_aes256gcm_decrypt (const guint8 key[32], const guint8 nonce[12], const guint8 * ct, gsize ct_len, guint8 * out, gsize * out_len)`; on the bytecode load path, detect the `FPB1` container and decrypt in memory before `JS_ReadObject`.

Context: white-box desktop; custom Frida build required (from T01). The AES-256 key is 32 bytes, unique per build, injected from a git-ignored file at build time — never committed, never written to disk at runtime. `gumjs_deps` in `subprojects/frida-gum/bindings/gumjs/meson.build` (dependencies: `gum_dep`, `gum_prof_dep`, `quickjs_dep`, `v8_dep`, `gio_dep`, `gio_os_package_dep`, `json_glib_dep`, `ffi_dep`, `sqlite_dep`) does not link any crypto library, so this task vendors a small, self-contained AES-256-GCM decryptor rather than adding a new dependency. Files in English; follow `CONTRIBUTING.md` C rules (high-level-first ordering, project brace/indent: opening brace of a function or block on its own line, space before `(`, `*` attached to the variable name). Plain shell/editor/git only.

- [ ] **Step 1: Confirm the current hook site before editing**

Run: `sed -n '644,660p' subprojects/frida-gum/bindings/gumjs/gumquickscriptbackend.c`

Expected: line 659 reads `  val = JS_ReadObject (ctx, code, size, JS_READ_OBJ_BYTECODE);` inside `gum_quick_script_backend_read_program()`. This confirms the line numbers used below still match.

- [ ] **Step 2: Create the AES-256-GCM decrypt header**

Create `subprojects/frida-gum/lib/prot/gumprotaesgcm.h`:

```c
#ifndef __GUM_PROT_AESGCM_H__
#define __GUM_PROT_AESGCM_H__

#include <glib.h>

G_BEGIN_DECLS

gboolean gum_prot_aes256gcm_decrypt (const guint8 key[32],
    const guint8 nonce[12], const guint8 * ct, gsize ct_len, guint8 * out,
    gsize * out_len);

G_END_DECLS

#endif
```

- [ ] **Step 3: Create the AES-256-GCM decrypt implementation**

Create `subprojects/frida-gum/lib/prot/gumprotaesgcm.c`:

```c
/*
 * Minimal, self-contained AES-256-GCM decryption for FPB1-protected agent
 * bytecode. GCM only needs the AES forward cipher (key expansion and
 * single-block encryption are used to generate the CTR-mode keystream and
 * the tag mask), so no inverse cipher is implemented. The forward cipher
 * below is a from-scratch implementation of the FIPS-197 algorithm.
 *
 * Licence: wxWindows Library Licence, Version 3.1
 */

#include "gumprotaesgcm.h"

#include <string.h>

#define GUM_PROT_AES_NK 8
#define GUM_PROT_AES_NR 14
#define GUM_PROT_AES_NB 4
#define GUM_PROT_AES_ROUND_KEY_SIZE \
    (GUM_PROT_AES_NB * (GUM_PROT_AES_NR + 1) * 4)
#define GUM_PROT_GCM_BLOCK_SIZE 16

typedef guint8 GumProtAesState[4][4];

static void gum_prot_aes256_expand_key (
    guint8 round_key[GUM_PROT_AES_ROUND_KEY_SIZE], const guint8 key[32]);
static void gum_prot_aes256_encrypt_block (
    const guint8 round_key[GUM_PROT_AES_ROUND_KEY_SIZE], guint8 block[16]);
static void gum_prot_aes256_add_round_key (guint8 round,
    GumProtAesState * state,
    const guint8 round_key[GUM_PROT_AES_ROUND_KEY_SIZE]);
static void gum_prot_aes256_sub_bytes (GumProtAesState * state);
static void gum_prot_aes256_shift_rows (GumProtAesState * state);
static void gum_prot_aes256_mix_columns (GumProtAesState * state);
static guint8 gum_prot_aes256_xtime (guint8 x);
static void gum_prot_gcm_mul (guint8 x[16], const guint8 y[16]);

static const guint8 gum_prot_aes_sbox[256] =
{
  0x63, 0x7c, 0x77, 0x7b, 0xf2, 0x6b, 0x6f, 0xc5, 0x30, 0x01, 0x67, 0x2b, 0xfe, 0xd7, 0xab, 0x76,
  0xca, 0x82, 0xc9, 0x7d, 0xfa, 0x59, 0x47, 0xf0, 0xad, 0xd4, 0xa2, 0xaf, 0x9c, 0xa4, 0x72, 0xc0,
  0xb7, 0xfd, 0x93, 0x26, 0x36, 0x3f, 0xf7, 0xcc, 0x34, 0xa5, 0xe5, 0xf1, 0x71, 0xd8, 0x31, 0x15,
  0x04, 0xc7, 0x23, 0xc3, 0x18, 0x96, 0x05, 0x9a, 0x07, 0x12, 0x80, 0xe2, 0xeb, 0x27, 0xb2, 0x75,
  0x09, 0x83, 0x2c, 0x1a, 0x1b, 0x6e, 0x5a, 0xa0, 0x52, 0x3b, 0xd6, 0xb3, 0x29, 0xe3, 0x2f, 0x84,
  0x53, 0xd1, 0x00, 0xed, 0x20, 0xfc, 0xb1, 0x5b, 0x6a, 0xcb, 0xbe, 0x39, 0x4a, 0x4c, 0x58, 0xcf,
  0xd0, 0xef, 0xaa, 0xfb, 0x43, 0x4d, 0x33, 0x85, 0x45, 0xf9, 0x02, 0x7f, 0x50, 0x3c, 0x9f, 0xa8,
  0x51, 0xa3, 0x40, 0x8f, 0x92, 0x9d, 0x38, 0xf5, 0xbc, 0xb6, 0xda, 0x21, 0x10, 0xff, 0xf3, 0xd2,
  0xcd, 0x0c, 0x13, 0xec, 0x5f, 0x97, 0x44, 0x17, 0xc4, 0xa7, 0x7e, 0x3d, 0x64, 0x5d, 0x19, 0x73,
  0x60, 0x81, 0x4f, 0xdc, 0x22, 0x2a, 0x90, 0x88, 0x46, 0xee, 0xb8, 0x14, 0xde, 0x5e, 0x0b, 0xdb,
  0xe0, 0x32, 0x3a, 0x0a, 0x49, 0x06, 0x24, 0x5c, 0xc2, 0xd3, 0xac, 0x62, 0x91, 0x95, 0xe4, 0x79,
  0xe7, 0xc8, 0x37, 0x6d, 0x8d, 0xd5, 0x4e, 0xa9, 0x6c, 0x56, 0xf4, 0xea, 0x65, 0x7a, 0xae, 0x08,
  0xba, 0x78, 0x25, 0x2e, 0x1c, 0xa6, 0xb4, 0xc6, 0xe8, 0xdd, 0x74, 0x1f, 0x4b, 0xbd, 0x8b, 0x8a,
  0x70, 0x3e, 0xb5, 0x66, 0x48, 0x03, 0xf6, 0x0e, 0x61, 0x35, 0x57, 0xb9, 0x86, 0xc1, 0x1d, 0x9e,
  0xe1, 0xf8, 0x98, 0x11, 0x69, 0xd9, 0x8e, 0x94, 0x9b, 0x1e, 0x87, 0xe9, 0xce, 0x55, 0x28, 0xdf,
  0x8c, 0xa1, 0x89, 0x0d, 0xbf, 0xe6, 0x42, 0x68, 0x41, 0x99, 0x2d, 0x0f, 0xb0, 0x54, 0xbb, 0x16
};

static const guint8 gum_prot_aes_rcon[11] =
{
  0x8d, 0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1b, 0x36
};

gboolean
gum_prot_aes256gcm_decrypt (const guint8 key[32],
                            const guint8 nonce[12],
                            const guint8 * ct,
                            gsize ct_len,
                            guint8 * out,
                            gsize * out_len)
{
  guint8 round_key[GUM_PROT_AES_ROUND_KEY_SIZE];
  guint8 h[16] = { 0, };
  guint8 j0[16];
  guint8 tag_state[16] = { 0, };
  guint8 counter[16];
  guint8 keystream[16];
  guint8 expected_tag[16];
  guint8 length_block[16] = { 0, };
  const guint8 * body;
  gsize body_len;
  guint64 body_bit_len;
  gsize i;
  guint8 diff;

  if (ct_len < GUM_PROT_GCM_BLOCK_SIZE)
    return FALSE;

  body = ct;
  body_len = ct_len - GUM_PROT_GCM_BLOCK_SIZE;

  gum_prot_aes256_expand_key (round_key, key);
  gum_prot_aes256_encrypt_block (round_key, h);

  memcpy (j0, nonce, 12);
  j0[12] = 0x00;
  j0[13] = 0x00;
  j0[14] = 0x00;
  j0[15] = 0x01;

  for (i = 0; i < body_len; i += GUM_PROT_GCM_BLOCK_SIZE)
  {
    guint8 block[16] = { 0, };
    gsize chunk = MIN (GUM_PROT_GCM_BLOCK_SIZE, body_len - i);
    gsize b;

    memcpy (block, body + i, chunk);
    for (b = 0; b != 16; b++)
      tag_state[b] ^= block[b];
    gum_prot_gcm_mul (tag_state, h);
  }

  body_bit_len = (guint64) body_len * 8;
  for (i = 0; i != 8; i++)
    length_block[8 + i] = (guint8) (body_bit_len >> (56 - i * 8));
  for (i = 0; i != 16; i++)
    tag_state[i] ^= length_block[i];
  gum_prot_gcm_mul (tag_state, h);

  memcpy (counter, j0, 16);
  gum_prot_aes256_encrypt_block (round_key, counter);
  for (i = 0; i != 16; i++)
    expected_tag[i] = tag_state[i] ^ counter[i];

  diff = 0;
  for (i = 0; i != 16; i++)
    diff |= expected_tag[i] ^ body[body_len + i];
  if (diff != 0)
    return FALSE;

  memcpy (counter, j0, 16);
  for (i = 0; i < body_len; i += GUM_PROT_GCM_BLOCK_SIZE)
  {
    gsize chunk = MIN (GUM_PROT_GCM_BLOCK_SIZE, body_len - i);
    gsize b;

    for (b = 16; b != 12; b--)
    {
      if (++counter[b - 1] != 0)
        break;
    }

    memcpy (keystream, counter, 16);
    gum_prot_aes256_encrypt_block (round_key, keystream);

    for (b = 0; b != chunk; b++)
      out[i + b] = body[i + b] ^ keystream[b];
  }

  *out_len = body_len;

  return TRUE;
}

static void
gum_prot_aes256_expand_key (guint8 round_key[GUM_PROT_AES_ROUND_KEY_SIZE],
                            const guint8 key[32])
{
  guint i, j, k;
  guint8 tempa[4];

  for (i = 0; i != GUM_PROT_AES_NK; i++)
  {
    round_key[(i * 4) + 0] = key[(i * 4) + 0];
    round_key[(i * 4) + 1] = key[(i * 4) + 1];
    round_key[(i * 4) + 2] = key[(i * 4) + 2];
    round_key[(i * 4) + 3] = key[(i * 4) + 3];
  }

  for (i = GUM_PROT_AES_NK; i != GUM_PROT_AES_NB * (GUM_PROT_AES_NR + 1); i++)
  {
    k = (i - 1) * 4;
    tempa[0] = round_key[k + 0];
    tempa[1] = round_key[k + 1];
    tempa[2] = round_key[k + 2];
    tempa[3] = round_key[k + 3];

    if (i % GUM_PROT_AES_NK == 0)
    {
      guint8 tmp = tempa[0];

      tempa[0] = gum_prot_aes_sbox[tempa[1]];
      tempa[1] = gum_prot_aes_sbox[tempa[2]];
      tempa[2] = gum_prot_aes_sbox[tempa[3]];
      tempa[3] = gum_prot_aes_sbox[tmp];

      tempa[0] ^= gum_prot_aes_rcon[i / GUM_PROT_AES_NK];
    }
    else if (i % GUM_PROT_AES_NK == 4)
    {
      tempa[0] = gum_prot_aes_sbox[tempa[0]];
      tempa[1] = gum_prot_aes_sbox[tempa[1]];
      tempa[2] = gum_prot_aes_sbox[tempa[2]];
      tempa[3] = gum_prot_aes_sbox[tempa[3]];
    }

    j = i * 4;
    k = (i - GUM_PROT_AES_NK) * 4;
    round_key[j + 0] = round_key[k + 0] ^ tempa[0];
    round_key[j + 1] = round_key[k + 1] ^ tempa[1];
    round_key[j + 2] = round_key[k + 2] ^ tempa[2];
    round_key[j + 3] = round_key[k + 3] ^ tempa[3];
  }
}

static void
gum_prot_aes256_encrypt_block (const guint8 round_key[GUM_PROT_AES_ROUND_KEY_SIZE],
                               guint8 block[16])
{
  GumProtAesState * state = (GumProtAesState *) block;
  guint8 round;

  gum_prot_aes256_add_round_key (0, state, round_key);

  for (round = 1; ; round++)
  {
    gum_prot_aes256_sub_bytes (state);
    gum_prot_aes256_shift_rows (state);
    if (round == GUM_PROT_AES_NR)
      break;
    gum_prot_aes256_mix_columns (state);
    gum_prot_aes256_add_round_key (round, state, round_key);
  }

  gum_prot_aes256_add_round_key (GUM_PROT_AES_NR, state, round_key);
}

static void
gum_prot_aes256_add_round_key (guint8 round,
                               GumProtAesState * state,
                               const guint8 round_key[GUM_PROT_AES_ROUND_KEY_SIZE])
{
  guint8 i, j;

  for (i = 0; i != 4; i++)
  {
    for (j = 0; j != 4; j++)
    {
      (*state)[i][j] ^=
          round_key[(round * GUM_PROT_AES_NB * 4) + (i * GUM_PROT_AES_NB) + j];
    }
  }
}

static void
gum_prot_aes256_sub_bytes (GumProtAesState * state)
{
  guint8 i, j;

  for (i = 0; i != 4; i++)
  {
    for (j = 0; j != 4; j++)
      (*state)[j][i] = gum_prot_aes_sbox[(*state)[j][i]];
  }
}

static void
gum_prot_aes256_shift_rows (GumProtAesState * state)
{
  guint8 temp;

  temp = (*state)[0][1];
  (*state)[0][1] = (*state)[1][1];
  (*state)[1][1] = (*state)[2][1];
  (*state)[2][1] = (*state)[3][1];
  (*state)[3][1] = temp;

  temp = (*state)[0][2];
  (*state)[0][2] = (*state)[2][2];
  (*state)[2][2] = temp;
  temp = (*state)[1][2];
  (*state)[1][2] = (*state)[3][2];
  (*state)[3][2] = temp;

  temp = (*state)[0][3];
  (*state)[0][3] = (*state)[3][3];
  (*state)[3][3] = (*state)[2][3];
  (*state)[2][3] = (*state)[1][3];
  (*state)[1][3] = temp;
}

static guint8
gum_prot_aes256_xtime (guint8 x)
{
  return (guint8) ((x << 1) ^ (((x >> 7) & 1) * 0x1b));
}

static void
gum_prot_aes256_mix_columns (GumProtAesState * state)
{
  guint8 i;

  for (i = 0; i != 4; i++)
  {
    guint8 a0 = (*state)[i][0];
    guint8 a1 = (*state)[i][1];
    guint8 a2 = (*state)[i][2];
    guint8 a3 = (*state)[i][3];
    guint8 sum = a0 ^ a1 ^ a2 ^ a3;

    (*state)[i][0] ^= sum ^ gum_prot_aes256_xtime (a0 ^ a1);
    (*state)[i][1] ^= sum ^ gum_prot_aes256_xtime (a1 ^ a2);
    (*state)[i][2] ^= sum ^ gum_prot_aes256_xtime (a2 ^ a3);
    (*state)[i][3] ^= sum ^ gum_prot_aes256_xtime (a3 ^ a0);
  }
}

static void
gum_prot_gcm_mul (guint8 x[16],
                  const guint8 y[16])
{
  guint8 z[16] = { 0, };
  guint8 v[16];
  gint i, j;

  memcpy (v, y, 16);

  for (i = 0; i != 16; i++)
  {
    for (j = 0; j != 8; j++)
    {
      gint k;
      guint8 carry_in;

      if ((x[i] >> (7 - j)) & 1)
      {
        for (k = 0; k != 16; k++)
          z[k] ^= v[k];
      }

      carry_in = v[15] & 1;
      for (k = 15; k != 0; k--)
        v[k] = (v[k] >> 1) | ((v[k - 1] & 1) << 7);
      v[0] >>= 1;
      if (carry_in)
        v[0] ^= 0xe1;
    }
  }

  memcpy (x, z, 16);
}
```

- [ ] **Step 4: Wire the new source file into the gumjs build**

Run: `grep -n "'gumquickscriptbackend.c'" subprojects/frida-gum/bindings/gumjs/meson.build`

Expected: one match, e.g. `    'gumquickscriptbackend.c',`.

Open `subprojects/frida-gum/bindings/gumjs/meson.build` and change that line from:

```
    'gumquickscriptbackend.c',
```

to:

```
    'gumquickscriptbackend.c',
    '../../lib/prot/gumprotaesgcm.c',
```

(the path is relative to `bindings/gumjs/meson.build`, i.e. `subprojects/frida-gum/lib/prot/gumprotaesgcm.c`; it is only added inside the `if quickjs_dep.found()` block, alongside the other QuickJS-only sources).

- [ ] **Step 5: Add the git-ignore for the generated key header**

Create `subprojects/frida-gum/lib/prot/.gitignore`:

```
gumprotkey.h
```

- [ ] **Step 6: Add the includes and forward declaration to `gumquickscriptbackend.c`**

Open `subprojects/frida-gum/bindings/gumjs/gumquickscriptbackend.c`. After the existing includes:

```c
#include <stdlib.h>
#include <string.h>
```

add:

```c
#include <stdlib.h>
#include <string.h>

#include "../../lib/prot/gumprotaesgcm.h"
#include "../../lib/prot/gumprotkey.h"
```

Then, after the `GUM_QUICKJS_BYTECODE_MAGIC` block:

```c
#if G_BYTE_ORDER == G_BIG_ENDIAN
# define GUM_QUICKJS_BYTECODE_MAGIC 0x42
#else
# define GUM_QUICKJS_BYTECODE_MAGIC 0x02
#endif
```

add:

```c
#define GUM_PROT_MAGIC_SIZE 4
#define GUM_PROT_NONCE_SIZE 12
#define GUM_PROT_TAG_SIZE 16
```

Then, right after the existing forward declaration:

```c
static JSValue gum_compile_module (JSContext * ctx, const GumESAsset * asset);
```

add:

```c
static JSValue gum_compile_module (JSContext * ctx, const GumESAsset * asset);
static GBytes * gum_prot_decrypt (const guint8 * data, gsize size);
```

- [ ] **Step 7: Add the `gum_prot_decrypt` helper**

In the same file, right before the definition of `gum_compile_module` (the `static JSValue\ngum_compile_module (JSContext * ctx,\n                    const GumESAsset * asset)` block), insert:

```c
static GBytes *
gum_prot_decrypt (const guint8 * data,
                  gsize size)
{
  const guint8 * nonce;
  const guint8 * ct;
  gsize ct_len;
  guint8 * plaintext;
  gsize plaintext_len;

  if (size < GUM_PROT_MAGIC_SIZE + GUM_PROT_NONCE_SIZE + GUM_PROT_TAG_SIZE)
    return NULL;

  if (data[0] != 'F' || data[1] != 'P' || data[2] != 'B' || data[3] != '1')
    return NULL;

  nonce = data + GUM_PROT_MAGIC_SIZE;
  ct = nonce + GUM_PROT_NONCE_SIZE;
  ct_len = size - GUM_PROT_MAGIC_SIZE - GUM_PROT_NONCE_SIZE;

  plaintext = g_malloc (ct_len - GUM_PROT_TAG_SIZE);

  if (!gum_prot_aes256gcm_decrypt (gum_prot_key, nonce, ct, ct_len, plaintext,
      &plaintext_len))
  {
    g_free (plaintext);
    return NULL;
  }

  return g_bytes_new_take (plaintext, plaintext_len);
}

```

Run: `grep -n "gum_prot_decrypt" subprojects/frida-gum/bindings/gumjs/gumquickscriptbackend.c`

Expected: three matches — the forward declaration, the definition, and none yet at the call sites (those are added next).

- [ ] **Step 8: Hook `gum_compile_module()`'s module-load path**

Replace this block inside `gum_compile_module()`:

```c
  if (((guint8 *) asset->data)[0] == GUM_QUICKJS_BYTECODE_MAGIC)
  {
    val = JS_ReadObject (ctx, asset->data, asset->data_size,
        JS_READ_OBJ_BYTECODE);
  }
  else
  {
    val = JS_Eval (ctx, asset->data, asset->data_size, asset->name,
        JS_EVAL_TYPE_MODULE | JS_EVAL_FLAG_STRICT | JS_EVAL_FLAG_COMPILE_ONLY);
  }
```

with:

```c
  plaintext = gum_prot_decrypt ((const guint8 *) asset->data, asset->data_size);
  if (plaintext != NULL)
  {
    gconstpointer code;
    gsize size;

    code = g_bytes_get_data (plaintext, &size);

    val = JS_ReadObject (ctx, code, size, JS_READ_OBJ_BYTECODE);

    g_bytes_unref (plaintext);
  }
  else if (((guint8 *) asset->data)[0] == GUM_QUICKJS_BYTECODE_MAGIC)
  {
    val = JS_ReadObject (ctx, asset->data, asset->data_size,
        JS_READ_OBJ_BYTECODE);
  }
  else
  {
    val = JS_Eval (ctx, asset->data, asset->data_size, asset->name,
        JS_EVAL_TYPE_MODULE | JS_EVAL_FLAG_STRICT | JS_EVAL_FLAG_COMPILE_ONLY);
  }
```

and add `GBytes * plaintext;` to `gum_compile_module()`'s declarations at the top of the function, next to the existing `JSValue val; JSModuleDef * mod; JSValue meta; gchar * url;`:

```c
  JSValue val;
  JSModuleDef * mod;
  JSValue meta;
  gchar * url;
  GBytes * plaintext;
```

- [ ] **Step 9: Hook `gum_quick_script_backend_read_program()`'s bytecode-load path**

Replace:

```c
  GumESProgram * program;
  JSValue val;
  gconstpointer code;
  gsize size;

  program = gum_es_program_new ();

  code = g_bytes_get_data (bytecode, &size);

  val = JS_ReadObject (ctx, code, size, JS_READ_OBJ_BYTECODE);

  if (JS_IsException (val))
    goto malformed_code;
```

with:

```c
  GumESProgram * program;
  JSValue val;
  gconstpointer code;
  gsize size;
  GBytes * plaintext;

  program = gum_es_program_new ();

  code = g_bytes_get_data (bytecode, &size);

  plaintext = gum_prot_decrypt (code, size);
  if (plaintext != NULL)
    code = g_bytes_get_data (plaintext, &size);

  val = JS_ReadObject (ctx, code, size, JS_READ_OBJ_BYTECODE);

  g_clear_pointer (&plaintext, g_bytes_unref);

  if (JS_IsException (val))
    goto malformed_code;
```

- [ ] **Step 10: Generate the embedded key header from the T07 key file**

Run this from the root of the `frida` repository (the key file `tools/protect/.key` was created by an earlier task; never commit it or the header it generates):

```sh
python3 -c "
data = open('tools/protect/.key', 'rb').read()
assert len(data) == 32, 'key must be 32 bytes'
items = ', '.join('0x%02x' % b for b in data)
with open('subprojects/frida-gum/lib/prot/gumprotkey.h', 'w') as f:
    f.write('#ifndef GUM_PROT_KEY_H\n')
    f.write('#define GUM_PROT_KEY_H\n\n')
    f.write('static const guint8 gum_prot_key[32] = { %s };\n\n' % items)
    f.write('#endif\n')
"
```

Run: `test -f subprojects/frida-gum/lib/prot/gumprotkey.h && wc -l subprojects/frida-gum/lib/prot/gumprotkey.h`

Expected: the file exists and reports `4` lines... plus blank lines (a handful of lines, non-empty).

- [ ] **Step 11: Build**

Run: `make`

Expected: exits with code 0. This compiles `gumprotaesgcm.c` into `frida-gumjs` and rebuilds `frida-python` against it.

- [ ] **Step 12: Phase-1b e2e gate — build a protected agent and load it under the custom Frida**

Run:

```sh
python tools/protect/build_protected.py tools/harness/sample_agent.js /tmp/agent.fpb
```

Expected: exits with code 0; `/tmp/agent.fpb` exists and its first 4 bytes are `FPB1` (check with `head -c4 /tmp/agent.fpb`).

Then, with `PYTHONPATH` set to the T01 build's installed `frida` module (see T02's step 2/4 for how to set it), run:

```sh
python3 -c "
import sys
sys.path.insert(0, 'tools/harness')
import roundtrip

with open('/tmp/agent.fpb', 'rb') as f:
    data = f.read()

print(roundtrip.run(data))
"
```

Expected: prints `ROUNDTRIP_OK`. This proves `gum_quick_script_backend_read_program()` detected the `FPB1` container, decrypted it with the embedded `gum_prot_key`, and fed the recovered plaintext bytecode to `JS_ReadObject`.

- [ ] **Step 13: Assert no plaintext bytecode file is produced on disk during load**

Run:

```sh
python3 -c "
import os
import sys
import tempfile

sys.path.insert(0, 'tools/harness')
import roundtrip

with open('/tmp/agent.fpb', 'rb') as f:
    data = f.read()

tmp_dir = tempfile.gettempdir()
before = sorted(os.listdir(tmp_dir))
roundtrip.run(data)
after = sorted(os.listdir(tmp_dir))

assert before == after, 'new file(s) appeared during load: %r' % (set(after) - set(before))
print('NO_PLAINTEXT_ON_DISK')
"
```

Expected: prints `NO_PLAINTEXT_ON_DISK`. The comparison passes because `gum_prot_decrypt()` and `gum_prot_aes256gcm_decrypt()` only allocate and write to in-memory buffers (`g_malloc`/`g_bytes_new_take`) — no file is opened for writing anywhere on the decrypt path.

- [ ] **Step 14: Phase-1b e2e gate — a build with a different key cannot decrypt the same `.fpb`**

Back up the current key header, then generate a header from a freshly-generated, different 32-byte key (never derived from `tools/protect/.key`):

```sh
cp subprojects/frida-gum/lib/prot/gumprotkey.h /tmp/gumprotkey.h.bak

python3 -c "
import os
data = os.urandom(32)
items = ', '.join('0x%02x' % b for b in data)
with open('subprojects/frida-gum/lib/prot/gumprotkey.h', 'w') as f:
    f.write('#ifndef GUM_PROT_KEY_H\n')
    f.write('#define GUM_PROT_KEY_H\n\n')
    f.write('static const guint8 gum_prot_key[32] = { %s };\n\n' % items)
    f.write('#endif\n')
"

make
```

Expected: `make` exits with code 0.

Run, against the same `/tmp/agent.fpb` produced in Step 12 (which was encrypted with the original key):

```sh
python3 -c "
import sys
sys.path.insert(0, 'tools/harness')
import roundtrip

with open('/tmp/agent.fpb', 'rb') as f:
    data = f.read()

try:
    print(roundtrip.run(data))
    sys.exit(1)
except Exception as e:
    print('DECRYPT_FAILED_AS_EXPECTED: %s' % e)
"
```

Expected: prints a line starting with `DECRYPT_FAILED_AS_EXPECTED:` (the wrong `gum_prot_key` makes `gum_prot_aes256gcm_decrypt()` fail its GCM tag check, `gum_prot_decrypt()` returns `NULL`, the raw `FPB1` container bytes are fed to `JS_ReadObject` as-is, and `JS_ReadObject` rejects them, raising the existing `malformed_code` `GError` — the same failure `gum_quick_script_backend_read_program()` already raises for any invalid bytecode, so an unmodified (vanilla) build of Frida fails to load this `.fpb` the same way).

- [ ] **Step 15: Restore the correct key and rebuild**

```sh
cp /tmp/gumprotkey.h.bak subprojects/frida-gum/lib/prot/gumprotkey.h
rm /tmp/gumprotkey.h.bak
make
```

Run:

```sh
python3 -c "
import sys
sys.path.insert(0, 'tools/harness')
import roundtrip

with open('/tmp/agent.fpb', 'rb') as f:
    data = f.read()

print(roundtrip.run(data))
"
```

Expected: prints `ROUNDTRIP_OK` again, confirming the tree is back to a working state with the correct key.

- [ ] **Step 16: Commit inside the `frida-gum` submodule**

The changed and new files all live inside the `frida-gum` submodule, so the commit is made there, not at the top-level `frida` repo. `gumprotkey.h` must never be staged — it is git-ignored by Step 5.

```sh
cd subprojects/frida-gum
git add lib/prot/gumprotaesgcm.h lib/prot/gumprotaesgcm.c lib/prot/.gitignore \
    bindings/gumjs/gumquickscriptbackend.c bindings/gumjs/meson.build
git status --porcelain
```

Expected: `git status --porcelain` lists only the five files just added, none of them named `gumprotkey.h`.

```sh
git commit -m "gumjs: Decrypt FPB1-protected bytecode before JS_ReadObject"
cd -
```

Run: `git -C subprojects/frida-gum log -1 --oneline -- bindings/gumjs/gumquickscriptbackend.c`

Expected: one line of output ending in `gumjs: Decrypt FPB1-protected bytecode before JS_ReadObject`.
### T09: Native-core skeleton + static link + GumJS glue (L1 scaffolding) [P]

**Depends:** T01

**Files:**
- Create: `subprojects/frida-gum/lib/prot/native_core.h`
- Create: `subprojects/frida-gum/lib/prot/native_core.c`
- Create: `subprojects/frida-gum/lib/prot/meson.build`
- Modify: `subprojects/frida-gum/meson.build` (add an include dir for `lib/prot` and a `subdir('lib' / 'prot')` call, alongside the existing `gum_incdirs` list and `subdir('gum')` ordering)
- Modify: `subprojects/frida-gum/gum/meson.build` (fold the new sources into `gum_sources` right before the `gum = library('frida-gum-' + api_version, ...)` call, so `native_core.c` compiles straight into the frida-gum library)
- Modify: `subprojects/frida-gum/bindings/gumjs/gumquickcore.c`, function `_gum_quick_core_init` (register the global `ProtNative` object there, next to where the `Script` global is registered), plus a new static function `gumjs_prot_native_call` defined in the same file
- Modify: `subprojects/frida-gum/tests/gumjs/script.c` (add the gate test case)

**Interfaces:**
- Consumes: build from T01
- Produces: C entry `int gum_prot_native_entry (const char * op, const char * arg, char * out, size_t out_len)` compiled INTO the frida-gum library (static; NO separate module); reachable from JS via a global `ProtNative.call(op, arg) -> string`.

Run every command below with your shell's current directory set to the `frida-gum` submodule. If you are at the meta-repo root, first run:

```
cd subprojects/frida-gum
```

- [ ] **Step 1: Create the native core header**

```
mkdir -p lib/prot
cat > lib/prot/native_core.h <<'EOF'
/*
 * Native core for the Prot white-box hardening layer.
 *
 * This is scaffolding: it wires a callable path from JavaScript down to
 * native code end-to-end. The real per-operation logic lands later.
 */

#ifndef __GUM_PROT_NATIVE_CORE_H__
#define __GUM_PROT_NATIVE_CORE_H__

#include <stddef.h>

int gum_prot_native_entry (const char * op, const char * arg, char * out,
    size_t out_len);

#endif
EOF
```

- [ ] **Step 2: Create the native core implementation**

```
cat > lib/prot/native_core.c <<'EOF'
#include "native_core.h"

#include <string.h>

int
gum_prot_native_entry (const char * op,
                       const char * arg,
                       char * out,
                       size_t out_len)
{
  (void) arg;

  if (out_len == 0)
    return -1;

  if (strcmp (op, "ping") == 0)
  {
    size_t n = strlen ("pong");

    if (n >= out_len)
      n = out_len - 1;

    memcpy (out, "pong", n);
    out[n] = '\0';

    return 0;
  }

  out[0] = '\0';

  return -1;
}
EOF
```

- [ ] **Step 3: Create the meson build file for `lib/prot`**

```
cat > lib/prot/meson.build <<'EOF'
gum_prot_sources = files(
  'native_core.c',
)
EOF
```

- [ ] **Step 4: Wire `lib/prot` into the top-level meson.build**

This adds `lib/prot` to the include search path used by the gum library and
everything linked against it, and enters the new subdirectory before `gum`
is built (so its sources are ready in time).

```
python3 - <<'PYEOF'
import pathlib

p = pathlib.Path("meson.build")
s = p.read_text()

old_incdirs = (
    "  include_directories('libs' / 'gum' / 'heap'),\n"
    "  include_directories('libs' / 'gum' / 'prof'),\n"
    "]\n"
)
new_incdirs = (
    "  include_directories('libs' / 'gum' / 'heap'),\n"
    "  include_directories('libs' / 'gum' / 'prof'),\n"
    "  include_directories('lib' / 'prot'),\n"
    "]\n"
)
assert s.count(old_incdirs) == 1, "gum_incdirs anchor not found"
s = s.replace(old_incdirs, new_incdirs)

old_subdirs = (
    "subdir('ext')\n"
    "subdir('gum')\n"
    "subdir('libs')\n"
)
new_subdirs = (
    "subdir('ext')\n"
    "subdir('lib' / 'prot')\n"
    "subdir('gum')\n"
    "subdir('libs')\n"
)
assert s.count(old_subdirs) == 1, "subdir ordering anchor not found"
s = s.replace(old_subdirs, new_subdirs)

p.write_text(s)
PYEOF
```

- [ ] **Step 5: Compile `native_core.c` into the frida-gum library**

```
python3 - <<'PYEOF'
import pathlib

p = pathlib.Path("gum/meson.build")
s = p.read_text()

old = (
    "if lzma_dep.found()\n"
    "  gum_internal_deps += lzma_dep\n"
    "endif\n"
    "\n"
    "gum = library('frida-gum-' + api_version, gum_sources + gum_enums,\n"
)
new = (
    "if lzma_dep.found()\n"
    "  gum_internal_deps += lzma_dep\n"
    "endif\n"
    "\n"
    "gum_sources += gum_prot_sources\n"
    "\n"
    "gum = library('frida-gum-' + api_version, gum_sources + gum_enums,\n"
)
assert s.count(old) == 1, "gum_sources anchor not found"
p.write_text(s.replace(old, new))
PYEOF
```

- [ ] **Step 6: Include the native core header in the QuickJS core binding**

```
python3 - <<'PYEOF'
import pathlib

p = pathlib.Path("bindings/gumjs/gumquickcore.c")
s = p.read_text()

old = (
    "#include \"gumquickstalker.h\"\n"
    "#include \"gumsourcemap.h\"\n"
)
new = (
    "#include \"gumquickstalker.h\"\n"
    "#include \"gumsourcemap.h\"\n"
    "#include \"native_core.h\"\n"
)
assert s.count(old) == 1, "include block anchor not found"
p.write_text(s.replace(old, new))
PYEOF
```

- [ ] **Step 7: Forward-declare the new JS function**

```
python3 - <<'PYEOF'
import pathlib

p = pathlib.Path("bindings/gumjs/gumquickcore.c")
s = p.read_text()

old = (
    "GUMJS_DECLARE_FUNCTION (gumjs_wait_for_event)\n"
    "\n"
    "GUMJS_DECLARE_GETTER (gumjs_frida_get_heap_size)\n"
)
new = (
    "GUMJS_DECLARE_FUNCTION (gumjs_wait_for_event)\n"
    "GUMJS_DECLARE_FUNCTION (gumjs_prot_native_call)\n"
    "\n"
    "GUMJS_DECLARE_GETTER (gumjs_frida_get_heap_size)\n"
)
assert s.count(old) == 1, "forward declaration anchor not found"
p.write_text(s.replace(old, new))
PYEOF
```

- [ ] **Step 8: Register the `ProtNative` global object**

This mirrors how the existing `Script` global is created a few lines above
it inside `_gum_quick_core_init`: a plain object with one method attached.

```
python3 - <<'PYEOF'
import pathlib

p = pathlib.Path("bindings/gumjs/gumquickcore.c")
s = p.read_text()

old = (
    "  obj = JS_NewObject (ctx);\n"
    "  JS_SetPropertyFunctionList (ctx, obj, gumjs_script_entries,\n"
    "      G_N_ELEMENTS (gumjs_script_entries));\n"
    "  JS_DefinePropertyValueStr (ctx, ns, \"Script\", obj, JS_PROP_C_W_E);\n"
)
new = (
    "  obj = JS_NewObject (ctx);\n"
    "  JS_SetPropertyFunctionList (ctx, obj, gumjs_script_entries,\n"
    "      G_N_ELEMENTS (gumjs_script_entries));\n"
    "  JS_DefinePropertyValueStr (ctx, ns, \"Script\", obj, JS_PROP_C_W_E);\n"
    "\n"
    "  obj = JS_NewObject (ctx);\n"
    "  JS_SetPropertyStr (ctx, obj, \"call\",\n"
    "      JS_NewCFunction (ctx, gumjs_prot_native_call, \"call\", 2));\n"
    "  JS_DefinePropertyValueStr (ctx, ns, \"ProtNative\", obj, JS_PROP_C_W_E);\n"
)
assert s.count(old) == 1, "Script registration anchor not found"
p.write_text(s.replace(old, new))
PYEOF
```

- [ ] **Step 9: Define `gumjs_prot_native_call`**

Placed right after `_gum_quick_core_init`, before the function that already
follows it in the file.

```
python3 - <<'PYEOF'
import pathlib

p = pathlib.Path("bindings/gumjs/gumquickcore.c")
s = p.read_text()

old = (
    "  JS_FreeValue (ctx, global_obj);\n"
    "\n"
    "  gum_exceptor_add (self->exceptor, gum_quick_core_handle_crashed_js, self);\n"
    "}\n"
    "\n"
    "static gboolean\n"
    "gum_quick_core_handle_crashed_js (GumExceptionDetails * details,\n"
)
new = (
    "  JS_FreeValue (ctx, global_obj);\n"
    "\n"
    "  gum_exceptor_add (self->exceptor, gum_quick_core_handle_crashed_js, self);\n"
    "}\n"
    "\n"
    "static JSValue\n"
    "gumjs_prot_native_call (JSContext * ctx,\n"
    "                        JSValueConst this_val,\n"
    "                        int argc,\n"
    "                        JSValueConst * argv)\n"
    "{\n"
    "  const char * op, * arg;\n"
    "  char out[4096];\n"
    "  JSValue result;\n"
    "\n"
    "  op = JS_ToCString (ctx, argv[0]);\n"
    "  arg = JS_ToCString (ctx, argv[1]);\n"
    "\n"
    "  gum_prot_native_entry (op, arg, out, sizeof (out));\n"
    "\n"
    "  JS_FreeCString (ctx, arg);\n"
    "  JS_FreeCString (ctx, op);\n"
    "\n"
    "  result = JS_NewString (ctx, out);\n"
    "\n"
    "  return result;\n"
    "}\n"
    "\n"
    "static gboolean\n"
    "gum_quick_core_handle_crashed_js (GumExceptionDetails * details,\n"
)
assert s.count(old) == 1, "_gum_quick_core_init end anchor not found"
p.write_text(s.replace(old, new))
PYEOF
```

- [ ] **Step 10: Add the gate test case**

```
python3 - <<'PYEOF'
import pathlib

p = pathlib.Path("tests/gumjs/script.c")
s = p.read_text()

old_entry = (
    "  TESTENTRY (message_can_be_sent)\n"
    "  TESTENTRY (message_can_be_sent_with_data)\n"
)
new_entry = (
    "  TESTENTRY (message_can_be_sent)\n"
    "  TESTENTRY (prot_native_ping_returns_pong)\n"
    "  TESTENTRY (message_can_be_sent_with_data)\n"
)
assert s.count(old_entry) == 1, "TESTENTRY anchor not found"
s = s.replace(old_entry, new_entry)

old_case = (
    "TESTCASE (message_can_be_sent)\n"
    "{\n"
    "  COMPILE_AND_LOAD_SCRIPT (\"send(1234);\");\n"
    "  EXPECT_SEND_MESSAGE_WITH (\"1234\");\n"
    "}\n"
    "\n"
    "TESTCASE (message_can_be_sent_with_data)\n"
)
new_case = (
    "TESTCASE (message_can_be_sent)\n"
    "{\n"
    "  COMPILE_AND_LOAD_SCRIPT (\"send(1234);\");\n"
    "  EXPECT_SEND_MESSAGE_WITH (\"1234\");\n"
    "}\n"
    "\n"
    "TESTCASE (prot_native_ping_returns_pong)\n"
    "{\n"
    "  COMPILE_AND_LOAD_SCRIPT (\"send(ProtNative.call('ping', ''));\");\n"
    "  EXPECT_SEND_MESSAGE_WITH (\"\\\"pong\\\"\");\n"
    "}\n"
    "\n"
    "TESTCASE (message_can_be_sent_with_data)\n"
)
assert s.count(old_case) == 1, "TESTCASE anchor not found"
s = s.replace(old_case, new_case)

p.write_text(s)
PYEOF
```

- [ ] **Step 11: Configure and build frida-gum with tests enabled**

```
./configure --enable-gumpp --enable-gumjs --enable-tests
make
```

Expected: the build finishes with no errors and produces the test binary at
`build/tests/gum-tests`.

- [ ] **Step 12: GATE — run the ping/pong check**

Run:

```
./build/tests/gum-tests /GumJS/Script/prot_native_ping_returns_pong#QJS
```

Expected: the output contains the line

```
/GumJS/Script/prot_native_ping_returns_pong#QJS: OK
```

and the command exits with status 0. This confirms that
`send(ProtNative.call('ping', ''))`, executed as a real QuickJS script
inside the freshly built frida-gum library, yields payload `"pong"`.

- [ ] **Step 13: Commit**

```
git add lib/prot/native_core.h lib/prot/native_core.c lib/prot/meson.build \
    meson.build gum/meson.build bindings/gumjs/gumquickcore.c \
    tests/gumjs/script.c
git commit -m "Add Prot native-core scaffolding and ProtNative JS glue"
```
### T10: Per-OS native obfuscation (Tigress) + Phase-2a gate (L1)

**Depends:** T09

**Files:**
- Create: `tools/protect/obfuscate_native.py`
- Modify: `subprojects/frida-gum/lib/prot/meson.build`

**Interfaces:**
- Consumes: native core + glue from T09.
- Produces: a per-OS Tigress pass over `native_core.c` wired into the build behind a build option; validation that a JS shim reaches the native core and `Process.enumerateModules()` shows no extra module.

- [ ] **Step 1: Create the Tigress wrapper script**

Create `tools/protect/obfuscate_native.py`:

```python
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
```

- [ ] **Step 2: Make it executable and sanity-check the missing-Tigress error**

```sh
chmod +x tools/protect/obfuscate_native.py
```

Run (on a machine without `tigress` on PATH, the common case):

```sh
tools/protect/obfuscate_native.py subprojects/frida-gum/lib/prot/native_core.c /tmp/native_core.obf.c
```

Expected: the script exits non-zero and prints an error containing `'tigress' not found on PATH`. It must not print a Python traceback.

- [ ] **Step 3: Add the `prot_obfuscate` build option**

Open `subprojects/frida-gum/meson.options` and append:

```meson
option('prot_obfuscate',
  type: 'boolean',
  value: false,
  description: 'Run native_core.c through Tigress source obfuscation before compiling',
)
```

- [ ] **Step 4: Wire the option into `lib/prot/meson.build`**

Run `cat subprojects/frida-gum/lib/prot/meson.build` to see the current content, then edit it:

1. Near the top of the file, add:

```meson
prot_obfuscate = get_option('prot_obfuscate')

if prot_obfuscate
  obfuscate_native = find_program(
    join_paths(meson.current_source_dir(), '..', '..', '..', '..',
      'tools', 'protect', 'obfuscate_native.py'))
  native_core_obf = custom_target('native_core_obf',
    input: 'native_core.c',
    output: 'native_core.obf.c',
    command: [obfuscate_native, '@INPUT@', '@OUTPUT@'],
  )
  prot_native_source = native_core_obf
else
  prot_native_source = files('native_core.c')
endif
```

2. Find the existing reference(s) to the literal filename `native_core.c` used as a compiled source in this file (in a `sources:` list, or a `static_library()`/`library()` call). Replace that literal `'native_core.c'` entry with `prot_native_source`, so the target compiles the Tigress output when `prot_obfuscate` is true and the plain file otherwise.

- [ ] **Step 5: Reconfigure and build with obfuscation enabled**

From the top-level `frida` repo:

```sh
./configure -Dprot_obfuscate=true
make
```

Expected: the build succeeds. If `tigress` is not installed on this machine, install it and put it on PATH first (Step 2 already confirmed the script's error message is clear in that case); the build must fail with that same message, not a raw stack trace, until `tigress` is available.

- [ ] **Step 6: Gate assertion 1 — functional (`ProtNative.call` reaches the obfuscated native core)**

Save this script as `/tmp/gate-functional.js`:

```js
send(ProtNative.call('ping', ''));
```

Run it with the `frida` CLI built by this repo, against any spawned process, e.g.:

```sh
frida -f /bin/ls -l /tmp/gate-functional.js --no-pause
```

Expected payload: the script's `send()` call transmits the message payload `"pong"` — the CLI prints the received message with payload `pong`. This must hold with the binary built from Step 5 (`-Dprot_obfuscate=true`).

- [ ] **Step 7: Gate assertion 2 — no standalone module for the native core**

Save this script as `/tmp/gate-no-module.js`:

```js
send(Process.enumerateModules().map(m => m.name));
```

Run it the same way:

```sh
frida -f /bin/ls -l /tmp/gate-no-module.js --no-pause
```

Expected payload: the received array of module names does not contain any entry equal to or containing `native_core` (no `native_core`, `native_core.so`, `native_core.obf`, or similar). The native core is statically linked into the frida-gum/agent binary, so it must not show up as its own module.

Both Step 6 and Step 7 must pass on the same `-Dprot_obfuscate=true` build for the Phase-2a gate to be considered met. This is the Phase-2a exit; porting the real logic into `native_core.c` (Phase-2b) is gated on the owner's scoping inventory and is out of scope here.

- [ ] **Step 8: Commit the submodule change**

```sh
cd subprojects/frida-gum
git add meson.options lib/prot/meson.build
git commit -m "prot: Add prot_obfuscate option wiring Tigress into native core build"
cd -
```

- [ ] **Step 9: Commit the root repo change**

```sh
git add tools/protect/obfuscate_native.py subprojects/frida-gum
git commit -m "protect: Add Tigress obfuscation script; bump frida-gum submodule"
```
---

## Later Phases (framed; gated — not yet task-decomposed)

These are intentionally framed milestones, not detailed tasks: each depends on a decision or
input not yet available. When its entry criteria are met, decompose it into `TNN` tasks the
same way as T01–T10 (sequential IDs, `Depends`, `[P]`, TDD steps, commits).

### Phase 2b — Native logic port (L1, chief lever) — GATED on the scoping inventory

**Entry criteria:** the owner completes the **scoping inventory** — a list of the agent's
functions/logic that must move to native, each with its inputs and outputs. Until this list
exists, Phase 2b cannot be sized (design §10).

**Scope when unblocked:** for each inventoried unit, port it from JS into the native core
(the `gum_prot_native_entry` dispatch established in T09), replace the JS implementation with
a `ProtNative.call(op, arg)` shim, and obfuscate via the T10 Tigress pass. Keep the JS shim
minimal.

**Done when:** the inventoried sensitive logic is absent from the JS bytecode and the agent
behaves identically; validated on the white-box red-team bar below.

### Phase 3 — Deep opcode-virtualization VM (L2, apex)

**Entry criteria:** Phases 1b + 2a complete; owner confirms L2 depth = **deep** (design §10).

**Scope:** replace straightforward QuickJS interpretation of the remaining JS with a bespoke,
re-encoded instruction set plus a custom interpreter loop in the QuickJS fork. Per design
§5-L2 the deep VM **subsumes** T05's opcode permutation — the permutation is retired, not
layered on. This is a very-high-effort sub-project; give it its own spec + plan.

**Done when:** the deep VM is in place, the agent runs correctly, and a time-boxed white-box
red-team cannot recover VM semantics within its budget.

### Phase 4 — Light anti-tamper (L5) + optional keys (L6)

**Entry criteria:** Phases 1–3 delivered.

**Scope:** L5 — integrity self-checks (hash the loaded bytecode + native core) and OS-level
anti-debug in the native core, understood as *nuisance-only* in white-box (the attacker holds
and can patch the binary). L6 — out of scope under the current assumption (no crypto keys); if
keys later appear, use embedded-key by default and treat the server-tethered variant as a
separate spec.

**Done when:** L5 checks are present and pass functional tests; L6 is a documented no-op
unless keys are introduced.

---

## Two-Tier Validation (applies to every phase gate)

- **Standard-tooling bar** (Phases 0 / 1a / 1b): an off-the-shelf QuickJS disassembler fails
  on the artifact; the agent runs on the custom Frida; original names/strings are absent.
- **White-box red-team bar** (Phases 2 / 3): a time-boxed red-team that patches the custom
  binary, reverses the dispatch loop / lifts the VM, and dumps RAM at runtime. Pass = the
  named reviewer cannot recover the protected logic within the agreed budget. A
  standard-tooling red-team does NOT validate Phase 2 or 3.

## Honest Ceiling

Even with every layer, an attacker holding the custom binary and controlling the machine can,
given enough expert time, dump decrypted bytecode from RAM, recover the permutation/keys from
the binary, lift the VM, and reverse the obfuscated native core. This plan raises that cost to
commercial-protector grade — the practical meaning of "strongest" here — not to impossibility.
