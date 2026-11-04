# Verification report

## Verdict: CHANGES_REQUIRED

All 14 delivered slices (S1–S10, S7X, F1, F3, F5) meet their stated acceptance criteria —
verified by re-running every hermetic test green in this session, by empirical re-derivation of
the F3 permutation guarantee against the true canonical header at the pinned fork commit, and by
code-reading the submodule hooks/glue against the plan. One seam gap remains between S1's README
(the build bring-up document) and S8's unconditional include of the git-ignored
`lib/prot/gumprotkey.h`: the committed tree plus README can no longer produce a build without an
undocumented step that lives only inside the plan document. That is the single fix below.

## Evidence

Commands run in this session (each → last meaningful output):

- `git diff --stat 783c61434b19 HEAD` → 22 files changed, 2654 insertions(+); the only non-tools
  change is the gitlink `subprojects/frida-gum -> f2918fd6` (F5 criterion).
- `python3 tools/protect/opcode_permute.py --self-test` → `self-test OK`, exit 0 (S5/F3
  criterion; covers bijection, pinned slots, determinism, seed sensitivity, the
  separated-pair loud failure, and no-write-on-guard-trip).
- `python3 tools/protect/test_scan_blob.py` → `ALL TESTS PASSED`, exit 0 (S4).
- `python3 tools/protect/test_encrypt_blob.py` → `OK`, exit 0 (S7: FPB1 magic, round-trip,
  wrong-key).
- `sh tools/protect/test_frida_env.sh` → `PASS`, exit 0, 18/18 ok cases incl. zsh, bash, POSIX sh,
  subdir cwd, unset-BASH_SOURCE emulation, direct execution, missing-build (F1).
- `sh tools/protect/test.sh` → `PASS`, exit 0 (S3: obfuscated output node-checks clean,
  ROUNDTRIP_OK absent).
- `tools/protect/obfuscate_native.py subprojects/frida-gum/lib/prot/native_core.c /tmp/…` →
  `obfuscate_native.py: 'tigress' not found on PATH. …`, exit 1, no traceback (S10 plan Step 2).
- F3 empirical: `git -C /tmp/qjs-verify show HEAD:quickjs-opcode.h` (true canonical at the pin;
  note `/tmp/qjs-verify`'s working-tree header was itself permuted by review r1-2 — the
  `.canonical`/`git show` copy is the trustworthy base) then `opcode_permute.py --seed
  deadbeefcafe01234567fedcba9876543 --quickjs /tmp/f3b` → `permuted 244 opcodes, 135 moved, 108
  held fixed`; `get_var_ref_check` DEF idx 100→100 and `put_var_ref_check` 101→101 (slot delta 0,
  canonically adjacent at lines 174/175, matching bellard stock lines 174/175) while 135 safe
  entries moved; DEF-name bijection 244 = 244. F3's four criteria all hold.
- Stock-commit match (S6 criterion 1): fork pin `/tmp/qjs-verify` @ `cd41bdbf…`
  `VERSION.txt` = `2026-06-04`; `/tmp/stock-quickjs` @ `3d5e064` ("new release") `VERSION` =
  `2026-06-04`. Chosen commit 3d5e064 is recorded in state.json's S6 retry notes — it matches the
  fork pin version, superseding the plan's stale 3f81070e/2024-01-13 as the criterion required.
- Submodule state: `git submodule status` → `f2918fd6…`; `git -C subprojects/frida-gum log` →
  `9980a1b6 Add Prot native-core scaffolding and ProtNative JS glue` (S9, plan message),
  `6631d2ac Limit prot_native gate test to the QuickJS runtime`, `1eac6928 gumjs: Decrypt
  FPB1-protected bytecode before JS_ReadObject` (S8, plan message), `88b4ef5c prot: Add
  prot_obfuscate option wiring Tigress into native core build` (S10, plan message), `df024653`
  (tests) then `f2918fd6` (fix) for F5; branches `devteam-S8/S9/S10` exist; submodule
  `status --porcelain` empty (gumprotkey.h never staged).
- Submodule code read against the plan: `gumquickscriptbackend.c` hooks both load paths
  (`gum_compile_module` and `gum_quick_script_backend_read_program`) with `gum_prot_decrypt` /
  FPB1 magic / nonce+tag layout exactly per T08 Steps 7–9; `gumjs/meson.build` adds
  `'../../lib/prot/gumprotaesgcm.c'` inside the `quickjs_dep.found()` block; `gumprotaesgcm.c`
  matches the plan's vendored FIPS-197 forward-cipher GCM decryptor; `meson.build` adds
  `include_directories('lib' / 'prot')` + `subdir('lib' / 'prot')` before `subdir('gum')`;
  `gum/meson.build:472` folds `gum_prot_sources` into the `frida-gum` library; `meson.options`
  gains `prot_obfuscate` (boolean, default false) and `lib/prot/meson.build` swaps in the
  Tigress `custom_target` only under that option; `gumquickcore.c` registers the `ProtNative`
  global with `gumjs_prot_native_call` (now with the F5 NULL checks on both `JS_ToCString`
  results and the two QJS-gated error tests); `tests/gumjs/script.c` carries
  `prot_native_ping_returns_pong` inside the `GUM_QUICK_IS_SCRIPT_BACKEND` gate.
- Recorded build evidence: `.claude/dev-team/logs/checkpoint-2.log` (checkpoint at ec12663a ==
  current HEAD) ends `[436/436] Linking target subprojects/frida-python/frida/_frida.abi3.so`
  … `EXIT=0`, compiling `.._lib_prot_native_core.c.o` (S9 wiring) and the S8 gumjs sources —
  the default (prot_obfuscate=false) build is unaffected (S10 criterion 3).
- Recorded engine proof evidence (state.json): S6 merged only after its verify
  (`STOCK_READER=/tmp/stock-quickjs/stock_reader ROUNDTRIP=tools/protect/roundtrip.sh
  SAMPLE_AGENT=tools/harness/sample_agent.js sh tools/protect/verify_disasm.sh`) passed,
  following two root-caused proof failures (macOS arm64e Mach-O attach streaks; retry notes
  require the gate to pass twice in a row — S6 criteria 3–4); F2/F5 gate record: `gum-tests ran
  1297 tests, ok 523/524, zero not ok, exit 0` (S9/F5 gum-tests criterion); S5's rebuild +
  roundtrip-on-permuted-build HARD gate and S8's e2e gates (ROUNDTRIP_OK,
  NO_PLAINTEXT_ON_DISK, wrong-key DECRYPT_FAILED_AS_EXPECTED + restore) are the slices' recorded
  merged-after-proof evidence.
- Could not run here (accepted on the recorded evidence above): a fresh `make` (the briefing's
  test command), `roundtrip.py`, `verify_disasm.sh`, `test_build_protected.py`'s happy path, and
  `gum-tests` — all require a 20–60 min custom build tree (uv CPython 3.12, `MACOS_CERTID=-`,
  and a generated `gumprotkey.h`) which no longer exists in any worktree or the main checkout.
- Hygiene: `git ls-files tools/protect` shows no `node_modules/`, `.seed`, or `.key`;
  `.gitignore` carries exactly `/tools/protect/node_modules/`, `/tools/protect/.seed`,
  `/tools/protect/.key` (S3/S5/S7 criteria); package-lock.json committed, node_modules not.
- Session decisions honored: wrap still pins `frida-forks/quickjs` @ `cd41bdbf…` (fork repoint
  deferred, documented in README "Deferred: GitHub fork"); Tigress functional gates (T10 Steps
  5–7) not run, deferred per the request.

## Findings

- [S1/S8 seam — README + build system] The documented build procedure is no longer sufficient:
  a fresh checkout following `tools/protect/README.md` "Building" fails to compile
  `gumquickscriptbackend.c`, which unconditionally includes `../../lib/prot/gumprotkey.h`
  (subprojects/frida-gum/bindings/gumjs/gumquickscriptbackend.c:19). That header is git-ignored
  by design (per-build key, never committed — correct), but no committed tool generates it and
  the README never mentions it (0 matches for gumprotkey/key-header); the generation snippet
  exists only inside `frida_plan/plans/2026-09-07-frida-agent-whitebox-hardening.md` (T08
  Step 10). This breaks the plan's own T01 deliverable ("a reproducible custom Frida build …
  with documented commands") for anyone without the plan open. → Add a small generator script
  (key file in, header out, wrong-length refusal, never echo the key) plus a README step, so
  the committed tree + README alone can produce a working build.
- [minor, no fix queued] The plan's checkbox ledger (`- [x]`) in
  `frida_plan/plans/2026-09-07-frida-agent-whitebox-hardening.md` was never ticked; the
  engine's state.json is the de-facto progress record. Documentation-only; noted for the
  owner, not queued.

No other requirement gaps found: every slice criterion listed in the briefing was either
re-verified green in this session or is covered by recorded engine proof (merged-after-verify)
plus code-reading that matches the plan verbatim where the plan pinned code. Reviews r1-1/r1-2
blockers (zsh source-path, JS_ToCString NULL crash, get_var_ref_check pair) are all confirmed
fixed in the delivered tree (F1, F5 @ f2918fd6, F3).

```json
{"fixes": [
  {"id": "F1", "title": "Make the committed tree buildable: script and document gumprotkey.h generation", "kind": "code", "files": ["tools/protect/gen_key_header.py", "tools/protect/test_gen_key_header.py", "tools/protect/README.md"], "criteria": ["python3 tools/protect/gen_key_header.py <key-file> writes subprojects/frida-gum/lib/prot/gumprotkey.h containing 'static const guint8 gum_prot_key[32] = { ... }' with exactly the 32 key bytes in 0x%02x form, wrapped in include guards", "the generator refuses key files whose length is not 32 bytes with a non-zero exit and a clear message, and never prints the key bytes to stdout/stderr", "python3 tools/protect/test_gen_key_header.py prints OK and exits 0, covering: header bytes equal the input key, wrong-length key refused non-zero, and the header path is reported as subprojects/frida-gum/lib/prot/gumprotkey.h", "tools/protect/README.md 'Building' section documents the required one-time step (create a 32-byte tools/protect/.key, run the generator) before make, and states the header is git-ignored and regenerated per build/release", "after running the documented steps, git check-ignore subprojects/frida-gum/lib/prot/gumprotkey.h exits 0 and the header content compiles as C (syntax check via clang -fsyntax-only with glib include path or equivalent)"], "deps": []}
]}
```
