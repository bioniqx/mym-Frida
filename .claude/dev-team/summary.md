## Summary
Execute frida_plan/plans/2026-09-07-frida-agent-whitebox-hardening.md T01-T10 with the session decisions (pin cd41bdbf, fork deferred, Tigress gate deferred)

## Changes
- **S7** (code) AEAD encrypt_blob (T07 part 1) — merged ef307a3d0
- **S1** (chore) Custom Frida build bring-up (T01, local) — merged e46059674
- **S9** (chore) Native-core skeleton + ProtNative glue (T09, L1 scaffolding) — merged c595d84b9
- **S2** (chore) Bytecode round-trip harness + sample agent (T02) — merged 236a128a3
- **S3** (chore) JS-source obfuscation CLI (T03, L4) — merged 306dc7854
- **S7X** (code) build_protected orchestrator (T07 part 2) — merged b630f11cb
- **S4** (code) Blob leak-scanner + Phase-1a gate (T04, L4) — merged 4607578d9
- **S5** (chore) QuickJS opcode permutation tool (T05, L3) — merged b2b07ffdd
- **S8** (chore) GumJS decrypt-before-read hook (T08, L3) — merged d51edf8c1
- **S10** (chore) Tigress wiring, gate deferred (T10) — merged 5164187a7
- **F1** (chore) Make frida_env.sh source-path detection work under zsh and POSIX sh — merged afba78562
- **F3** (chore) Constrain get_var_ref_check/put_var_ref_check pair in opcode permutation — merged 61584496b
- **F5** (chore) Land JS_ToCString NULL fix via gitlink (chore) — merged e74f66be6
- **S6** (chore) Stock-disassembler-fails gate (T06, L3) — merged ec12663af
- **F6** (code) Make the committed tree buildable: script and document gumprotkey.h generation — merged 5091d3902

## Verification
- review r1: CHANGES_REQUIRED (8 slices, 2 shard(s))
- review r2: APPROVED (6 slices, 1 shard(s))
- intent verification (glm-team-leader): CHANGES_REQUIRED
- last full-suite checkpoint: pass @ ec12663af

## Diff stat
```
.gitignore                            |    3 +
 subprojects/frida-gum                 |    2 +-
 tools/harness/roundtrip.py            |  195 ++++++
 tools/harness/sample_agent.js         |    1 +
 tools/protect/README.md               |  126 ++++
 tools/protect/build_protected.py      |   54 ++
 tools/protect/encrypt_blob.py         |   24 +
 tools/protect/frida_env.sh            |   54 ++
 tools/protect/gen_key_header.py       |   45 ++
 tools/protect/obfuscate.mjs           |   26 +
 tools/protect/obfuscate_native.py     |   63 ++
 tools/protect/opcode_permute.py       |  307 ++++++++++
 tools/protect/package-lock.json       | 1089 +++++++++++++++++++++++++++++++++
 tools/protect/package.json            |   10 +
 tools/protect/roundtrip.sh            |   74 +++
 tools/protect/scan_blob.py            |   43 ++
 tools/protect/stock_reader.c          |  153 +++++
 tools/protect/test.sh                 |   16 +
 tools/protect/test_build_protected.py |   89 +++
 tools/protect/test_encrypt_blob.py    |   61 ++
 tools/protect/test_frida_env.sh       |  170 +++++
 tools/protect/test_gen_key_header.py  |  142 +++++
 tools/protect/test_scan_blob.py       |   61 ++
 tools/protect/verify_disasm.sh        |   52 ++
 24 files changed, 2859 insertions(+), 1 deletion(-)
```
