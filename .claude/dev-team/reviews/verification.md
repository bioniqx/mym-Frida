# Verification briefing (MODE: VERIFICATION)

## Original request
Execute frida_plan/plans/2026-09-07-frida-agent-whitebox-hardening.md T01-T10 with the session decisions (pin cd41bdbf, fork deferred, Tigress gate deferred)

## Delivered slices and their acceptance criteria
- S1 — Custom Frida build bring-up (T01, local) (risk low)
  - configure -Dfrida_python=enabled and make exit 0 in the worktree (tail pasted)
  - git -C subprojects/frida-gum/subprojects/quickjs rev-parse HEAD prints cd41bdbf0c6c14a22f4a514bfe8efd6cbca50af3 fetched from the existing wrap
  - python3 -c 'import frida' succeeds after . tools/protect/frida_env.sh
  - README documents build commands, the pin, the deferred fork repoint step, and PYTHONPATH usage
- S2 — Bytecode round-trip harness + sample agent (T02) (risk low)
  - RED shown first: stub compile() raises NotImplementedError when run (plan Step 2 evidence)
  - GREEN: roundtrip.py CLI prints ROUNDTRIP_OK and exits 0
  - compile returns bytes containing the QuickJS bytecode magic first byte
- S3 — JS-source obfuscation CLI (T03, L4) (risk low)
  - RED shown first: test.sh fails with Cannot find module obfuscate.mjs (plan Step 2)
  - GREEN: sh tools/protect/test.sh prints PASS exit 0
  - .gitignore gains tools/protect/node_modules/, tools/protect/.seed, tools/protect/.key (front-loaded for S5/S7)
  - package-lock.json committed (node_modules never)
- S4 — Blob leak-scanner + Phase-1a gate (T04, L4) (risk low)
  - RED: test_scan_blob.py fails before implementation (exit!=1 assertions)
  - GREEN: python3 tools/protect/test_scan_blob.py prints ALL TESTS PASSED
  - Gate evidence: scan of obfuscated-sample blob CLEAN for LOCAL_NAME + ROUNDTRIP_OK; scan of plain blob LEAKED: ROUNDTRIP_OK (plan Steps 5-10)
- S5 — QuickJS opcode permutation tool (T05, L3) (risk high)
  - self-test passes (bijection, pinned slots, determinism, seed sensitivity)
  - CONSTRAINED_OPCODES re-derived from the ACTUAL fork checkout at cd41bdbf: grep -nE 'OP_[a-z0-9_]+ *[-+]' quickjs.c and range comparisons (plan Steps 3-4, 10); plan's starter list extended with every name found
  - Applied run prints permuted N opcodes, M moved, K held fixed; bijection diff empty; constrained check prints no MOVED (Steps 12-14)
  - Rebuilt make exit 0 AND roundtrip.py prints ROUNDTRIP_OK on the permuted build (Step 16 HARD gate)
  - .seed generated locally, never committed; permuted quickjs-opcode.h not committed (build artifact)
- S6 — Stock-disassembler-fails gate (T06, L3) (risk low)
  - stock QuickJS cloned at the bellard commit MATCHING the fork pin version (read the version from subprojects/frida-gum/subprojects/quickjs; plan's 3f81070e is for 2024-01-13 and may be stale - record the chosen commit in the report)
  - libquickjs.bignum.a builds; stock_reader compiles (macOS clang, no -ldl) and control run prints PARSED_OK
  - verify_disasm.sh ends with L3 GATE PASSED (4 checks) in your worktree with its own permuted build
  - roundtrip.sh adapter implements compile <src> <out.bin> and run <blob> over tools/harness/roundtrip.py and is what verify_disasm.sh calls via ROUNDTRIP env
- S7 — AEAD encrypt_blob (T07 part 1) (risk low)
  - RED: ModuleNotFoundError before implementation
  - GREEN: python3 tools/protect/test_encrypt_blob.py prints OK
  - round-trip and wrong-key tests both hold (plan Step 1 tests)
- S7X — build_protected orchestrator (T07 part 2) (risk low)
  - RED: subprocess non-zero before implementation
  - GREEN: python3 tools/protect/test_build_protected.py prints OK (produces FPB1-prefixed artifact)
  - output container starts with b'FPB1'
- S9 — Native-core skeleton + ProtNative glue (T09, L1 scaffolding) (risk high)
  - all T09 files created/edited per plan (lib/prot/native_core.{h,c}, lib/prot/meson.build, meson.build include+subdir, gum/meson.build source fold, gumquickcore.c glue, tests/gumjs/script.c case)
  - ./build/tests/gum-tests /GumJS/Script/prot_native_ping_returns_pong#QJS prints OK exit 0
  - inner submodule commit made with plan message; pushed to refs/heads/devteam-S9 of the main nested repo; top-level gitlink committed via commit-work
- S8 — GumJS decrypt-before-read hook (T08, L3) (risk high)
  - vendored AES-256-GCM decryptor + FPB1 hook land per plan (gumprotaesgcm.{h,c}, lib/prot/.gitignore, gumquickscriptbackend.c both load paths, gumjs meson.build)
  - e2e: build_protected -> run prints ROUNDTRIP_OK (plan Step 12)
  - NO_PLAINTEXT_ON_DISK (Step 13)
  - wrong-key build prints DECRYPT_FAILED_AS_EXPECTED then restored build prints ROUNDTRIP_OK again (Steps 14-15)
  - inner submodule commit with plan message; pushed to devteam-S8; top-level gitlink via commit-work; gumprotkey.h never staged
- S10 — Tigress wiring, gate deferred (T10) (risk low)
  - obfuscate_native.py runs, exits non-zero with the 'not found on PATH' message and no traceback (plan Step 2)
  - meson.options gains prot_obfuscate (default false); lib/prot/meson.build compiles native_core.obf.c only when true (plan Step 4)
  - default build (option false) unaffected: configure + make exit 0 in the worktree
  - Tigress functional gates (plan Steps 5-7) explicitly DEFERRED - listed as not run in the report
  - inner commit pushed to devteam-S10; top-level script + gitlink committed
- F1 — Make frida_env.sh source-path detection work under zsh and POSIX sh (risk low)
  - Sourcing from zsh and from bash in a worktree whose build/ exists exports PYTHONPATH starting with that worktree's build/subprojects/frida-python (asserted by test_frida_env.sh for both shells and from a subdirectory cwd)
  - When the script cannot determine its own path it fails fast with an error naming the actual repo root, never computing a srcroot from an empty BASH_SOURCE (regression case in test_frida_env.sh: unset BASH_SOURCE emulation / direct execution)
  - When build/subprojects/frida-python/frida/__init__.py is missing the message points at the correct repo root (test_frida_env.sh missing-build case)
  - sh tools/protect/test_frida_env.sh prints PASS and exits 0
- F3 — Constrain get_var_ref_check/put_var_ref_check pair in opcode permutation (risk low)
  - CONSTRAINED_OPCODES contains get_var_ref_check and put_var_ref_check
  - self-test still prints self-test OK (bijection, pinned slots, determinism, seed sensitivity)
  - applying a permutation to a copy of the fork's quickjs-opcode.h at cd41bdbf keeps get_var_ref_check and put_var_ref_check each at their canonical DEF slot (slot-index delta 0) while other safe opcodes still move
  - the tool fails loudly (non-zero exit, clear message) if a permutation would separate any canonically adjacent pair among the constrained get/put/set families it exists to protect
- F5 — Land JS_ToCString NULL fix via gitlink (chore) (risk low)
  - nested subprojects/frida-gum at f2918fd6 from branch devteam-F2 (fetch from /Users/ethan/Documents/GitHub/frida/subprojects/frida-gum); history df024653 tests then f2918fd6 fix
  - gum-tests full suite zero not-ok in your worktree incl. prot_native cases
  - top-level gitlink committed via commit-work at f2918fd6; gumprotkey.h from fresh local key never staged

## Changed files
`git diff --stat 783c61434b19 HEAD`

## Tests
`make`

## Output
Write the report to /Users/ethan/Documents/GitHub/frida/.claude/dev-team/reviews/verification.report.md; reply with the verdict line only. For each gap add a fix in a ```json {"fixes": [...]} block (title, files, criteria) so the Conductor can queue it.