# Frida Agent Hardening — Protecting a QuickJS Bytecode Agent Against Decompilation (White-Box Desktop)

**Status:** Draft for review
**Date:** 2026-09-07
**Owner:** Ethan
**Threat model class:** Full white-box, desktop (Linux / Windows / macOS)

---

## 1. Goal & non-goals

**Goal.** Make a Frida JavaScript agent — the source of which is compiled to QuickJS
bytecode and shipped together with a custom Frida build — as resistant to
reverse-engineering / decompilation as is realistically achievable, so that recovering
the agent's original logic costs a determined expert weeks of work rather than minutes
with off-the-shelf tooling.

**Explicit non-goal (honest ceiling).** *Absolute* un-decompilability is impossible under
this threat model. The attacker controls the machine, holds the custom Frida binary, and
can attach a debugger or a second Frida to dump decrypted state from RAM. Every scheme
here **raises cost**; none makes recovery impossible. "Strongest" is defined as
*commercial-protector-grade* (VMProtect / Themida / Tigress class), not "unbreakable".

---

## 2. Threat model

The attacker has, simultaneously:

- The **custom Frida binary** (so: the permuted opcode table, any embedded keys, the
  decrypt-before-load routine, the VM interpreter — all present in the binary).
- The **shipped protected artifact** (encrypted bytecode blob and/or native module).
- **Full control of a desktop OS**: ability to run a debugger, ptrace/attach, a second
  Frida instance, memory dumpers, and to *patch the custom Frida binary itself*.
- Unlimited offline time.

The attacker's objective is to recover the agent's source-level logic.

**Consequences that drive the design:**

1. Any check that acts as a *bypassable gate* (naive anti-debug, "is another Frida
   attached?") is worth little: the attacker patches it out of the binary they hold.
   → Do not invest in gates; invest in raising *comprehension cost*.
2. Bytecode must be decrypted into RAM to execute → it is always dumpable at runtime.
   → The only durable protection for logic is to **not represent that logic as
   recoverable bytecode** — i.e. move it to obfuscated native code and/or virtualize it.

---

## 3. Frida-specific facts grounding this design (verified in-repo)

- Frida embeds **Bellard's QuickJS fork** (`frida/quickjs.git`), version `2024-01-13`,
  pinned by commit and pulled as a Meson subproject wrap at configure time.
- The **opcode table is stock** (`quickjs-opcode.h` unmodified vs upstream; `BC_VERSION`
  and `BC_TAG_*` byte-for-byte identical). A stock QuickJS `2024-01-13` disassembler built
  with `CONFIG_BIGNUM` will therefore parse Frida-produced bytecode. **This is the primary
  weakness.**
- QuickJS bytecode still embeds **atoms (identifier / property names) and string
  literals** even after compilation — the single biggest source-level leak.
- User pipeline: `Session.compile_script(source)` → `JS_WriteObject(…, JS_WRITE_OBJ_BYTECODE)`
  produces the blob; `Session.create_script_from_bytes(bytes)` →
  `JS_ReadObject(…, JS_READ_OBJ_BYTECODE)` loads it. Bytecode is **QuickJS-only** (the V8
  backend explicitly refuses both compile and load).
- Frida Gadget **auto-detects** a bytecode file by its leading magic byte and loads it
  directly, so distribution as a `.qjs`-style blob is natural.
- `frida-compile` performs **minification only** (esbuild identifier/whitespace/syntax) —
  **no real obfuscation, no bytecode**. It is an independent pipeline.
- Running protected bytecode therefore *requires a custom Frida build* — accepted by the
  owner.

---

## 4. Core strategy

Defense-in-depth, ordered by **comprehension cost per unit of effort** rather than by how
"clever" a layer sounds. For this white-box/entire-logic/desktop case the ordering is:

1. **Move logic out of JS into obfuscated native code** (durable — attacks comprehension).
2. **Virtualize the remaining JS's execution** (durable — cannot be patched out).
3. **Permute + encrypt the bytecode** (kills off-the-shelf tooling — cheap baseline).
4. **Obfuscate JS source before compilation** (closes the name/string leak — cheap).
5. **Anti-tamper** (nuisance only in white-box — kept light, no false confidence).
6. **White-box crypto** (only if cryptographic keys must live in the artifact).

The single most important design decision: **the more of the agent's logic that lives in
native code (Layer 1), the stronger the result.** Layers 2–6 protect whatever must remain
JS; they are a fallback for the part that cannot be nativized, not a substitute for
Layer 1.

**Two orderings, deliberately different.** This section ranks layers by *conceptual
priority* (durability — L1 and L2 matter most). §9 ranks by *delivery sequencing*
(value-per-effort and dependencies — the cheap baselines L3/L4 ship first). These are not
competing recommendations.

---

## 5. Layered architecture

For each layer: *what it is · how · where it touches the tree · effort · value here ·
residual risk.*

### L1 — Native extraction + native-code obfuscation  ★ chief lever

- **What.** Re-express the sensitive logic as a **native Gum module in C** (using Gum's C
  API — `Interceptor`, `Memory`, `Module`, etc. all exist in C, not only JS). The JS agent
  shrinks to a thin loader/glue shim that hands control to native as early as possible.
- **How.** Compile the C with a code-obfuscating toolchain: an LLVM-based obfuscator
  (OLLVM / Hikari / Arkari) or a source-to-source obfuscator (Tigress, which targets x86
  well and is convenient cross-OS) — enabling control-flow flattening, bogus control flow,
  instruction substitution, and string encryption; then strip all symbols. **Default
  toolchain:** Tigress (source-level, cross-OS, x86-friendly); an LLVM-family obfuscator
  (OLLVM / Hikari / Arkari) is the alternative when an LLVM-IR pipeline is preferred.
- **Where.** New native module built alongside `frida-gum`; new glue in the GumJS QuickJS
  bindings to expose/load it; the owner's agent is split into `native core` + `JS shim`.
- **Packaging (decided).** The obfuscated native core is **statically linked into the
  custom Frida build**, not shipped as a standalone `.so` / `.dylib` / `.dll`. A separate
  module would be discoverable and dumpable by a second Frida (`Module.enumerateModules`),
  undercutting L1's comprehension-cost goal; linking it into the code-signed binary leaves
  no distinct module to locate and lets the binary signature carry integrity, so the native
  core needs **no separate at-rest encryption** (obfuscation + in-binary is the accepted
  posture). Trade-off accepted: native-core updates require a full binary rebuild and
  re-sign.
- **Effort.** High (requires rewriting logic in C/Gum + standing up an obfuscation
  toolchain per OS).
- **Value.** Highest and most durable. Native machine code obfuscated this way is far
  costlier to understand than QuickJS bytecode.
- **Residual risk.** Native code is still RE-able; obfuscation raises cost, not
  impossibility. Runtime behavior is still observable via tracing.

### L2 — Opcode virtualization / bespoke VM  ★ apex JS-side layer

- **What.** For logic that must stay JS, replace straightforward QuickJS interpretation
  with a **custom virtualized opcode scheme** — a bespoke VM whose semantics the attacker
  must reverse from scratch even with the binary in hand (the VMProtect idea applied to
  QuickJS).
- **How.** Two depths exist: (a) *shallow* — handler/dispatch indirection layered over the
  existing opcode semantics; (b) *deep* — a genuinely re-encoded instruction set with a
  custom interpreter loop in the QuickJS fork. **Target for "strongest" = deep**; shallow
  does not deliver the "reverse from scratch" property (the underlying op stream is
  unchanged) and is only a fallback if deep proves infeasible. Tracked as an open question
  in §10.
- **Composition with L3.** The deep VM's re-encoding **subsumes** L3's opcode permutation:
  L3 is the cheap Phase-1b baseline; when the deep VM lands it *replaces* the permutation
  rather than stacking on it, so the fork work done in Phase 1b is interim, not reworked
  twice.
- **Where.** The QuickJS fork (`frida/quickjs`) interpreter + writer/reader.
- **Effort.** Very high (deep) / high (shallow).
- **Value.** High and durable in white-box: unlike anti-tamper, a VM **cannot be patched
  out** — its semantics must be understood to run at all.
- **Residual risk.** A determined reverser can still lift the VM (published techniques
  exist for commercial VMs); it buys time, not permanence. Runtime perf cost.

### L3 — Opcode permutation + bytecode encryption + serialization transform  ★ cheap baseline

- **What.** (a) **Permute the QuickJS opcode numbering** in the fork so a stock
  disassembler mis-decodes everything and the bytecode only runs on this Frida; (b)
  **encrypt the bytecode blob** at rest with an AEAD cipher (e.g. AES-256-GCM or
  ChaCha20-Poly1305), decrypting in-memory immediately before `JS_ReadObject`; (c) optionally transform the serialized byte stream (XOR/shuffle).
- **How.** Reorder the `DEF(...)` entries in `quickjs-opcode.h` behind a secret seed
  (compiler emitters and interpreter dispatch stay internally consistent, so the runtime
  is unaffected); add a decrypt hook on the `create_script_from_bytes` / module-load path
  in the GumJS QuickJS backend; regenerate GumJS's own runtime bytecode with the same
  custom build so it stays consistent.
- **Where.** `frida/quickjs` fork + `frida-gum` GumJS QuickJS backend + build glue.
- **Effort.** Moderate, mostly mechanical (one-time), recurring on Frida bumps.
- **Value.** Immediately defeats all off-the-shelf QuickJS tooling. Necessary baseline.
- **Residual risk.** The permutation + key are recoverable from the binary the attacker
  holds (RE the dispatch loop). Value comes from combining with L1/L2, not standing alone.

### L4 — JS-source obfuscation before compilation  ★ cheap leak-plugging

- **What.** Run the remaining JS through a real obfuscator (identifier renaming +
  string-array encryption + dead-code / control-flow tricks) **before** `compile_script`,
  so the atoms and string literals embedded in the bytecode are not the real names/strings.
- **How.** Insert an obfuscation step (e.g. javascript-obfuscator) into the build pipeline
  ahead of bytecode compilation. Independent of the Frida runtime.
- **Where.** Build tooling only (no Frida change).
- **Effort.** Low.
- **Value.** Closes the largest bytecode leak (names + literals) cheaply.
- **Residual risk.** Recoverable at runtime; string decryption logic is present in the
  dumped bytecode unless paired with L1/L2.

### L5 — Anti-tamper / anti-analysis  ★ kept deliberately light

- **What.** Integrity self-checks (hash the loaded bytecode + native module), OS-level
  anti-debug (ptrace self-attach on Linux; `PT_DENY_ATTACH`/sysctl on macOS;
  PEB/`IsDebuggerPresent` on Windows), second-instrumentation detection.
- **How / where.** Native module (L1) startup checks.
- **Effort.** Low–moderate.
- **Value.** **Low in this threat model** — the attacker holds the binary and patches these
  gates out. Included only to deter casual/lazy inspection; must not create false
  confidence.
- **Residual risk.** Fully bypassable by a binary-holding attacker.

### L6 — White-box crypto / key handling  ★ conditional

- **What.** If the agent contains cryptographic keys/secrets, protect them with white-box
  crypto so keys never appear in cleartext in RAM. Optionally, **server-tethered key
  delivery**: the bytecode-decryption key is fetched at runtime from a server the owner
  controls, so the secret is not fully local (raises the bar: attacker must be online and
  intercept, and still only reaches decrypted state, not the key at rest).
- **How / where.** Native module + optional network component.
- **Effort.** High (white-box crypto) / moderate (server-tethered key).
- **Value.** High *if and only if* there are keys to protect; otherwise skip.
- **Residual risk.** Decrypted plaintext still transits RAM at use.

---

## 6. Build & distribution pipeline

Producing a protected artifact:

1. **Author** logic split: native core (C/Gum) + thin JS shim.
2. **Obfuscate** the JS shim (L4).
3. **Compile native core** with the obfuscating toolchain per target OS (L1); strip.
4. **Compile the JS shim to bytecode** using the *custom* Frida build (permuted opcodes /
   VM — L2/L3).
5. **Encrypt** the bytecode blob (L3).
6. **Ship** the custom Frida build (with the obfuscated native core statically linked in —
   see L1) plus the encrypted bytecode blob.

At runtime the custom Frida decrypts the blob in memory, loads it via `JS_ReadObject`, and
the shim hands control to the native core.

**Key management.** The permutation seed and encryption keys are build secrets, generated
**unique per build/release** (never a single reused value — that would be
break-once-run-everywhere). The **in-scope default is an embedded key** in the custom Frida
binary (offline; recoverable from the binary, but combined with L1/L2 the binary itself is
the costly part). The **server-tethered key** variant (key fetched at runtime from a server
the owner controls) is stronger but adds a network subsystem with its own auth / availability
/ rotation concerns — **deferred to its own spec** (see §7).

---

## 7. Component boundaries (units)

- **QuickJS fork** — opcode permutation (L3), VM (L2), decrypt-before-read hook. Isolated
  behind the existing `quickjs` Meson subproject.
- **frida-gum GumJS QuickJS backend** — decrypt hook wiring + native-module glue. Changes
  confined to the bytecode read/load path.
- **Native core toolchain** — a reproducible per-OS build of the obfuscated C module,
  independent of Frida's own build.
- **Build tooling** — obfuscation + encryption + packaging steps; a single command that
  turns `source + native core` into a shippable artifact.
- **Owner's agent** — native core (C) vs JS shim; the native boundary is a *parameter* of
  this design (see §10 assumption).
- **(Deferred) Server-tethered key subsystem** — only if the server-tethered key model (§6)
  is chosen. It is **out of scope for this spec** and needs its own design (key delivery,
  auth, availability, rotation); it is therefore not counted in §8 maintenance.

Each unit is independently testable (see §9).

---

## 8. Maintenance cost (must be accepted explicitly)

- The QuickJS fork (permutation + VM + decrypt) is **re-applied on every Frida/QuickJS
  version bump**. Mechanical but recurring. Recommended: **freeze on a pinned Frida
  version** and bump deliberately.
- The obfuscation toolchain (OLLVM/Tigress) must be maintained per OS and per Frida
  toolchain change.
- Bytecode is bound to the exact QuickJS build — artifacts must be rebuilt when Frida is
  bumped.

---

## 9. Phased delivery & success criteria

Ordered by value-per-effort and dependencies, so early phases already ship meaningful
protection. This delivery order intentionally differs from §4's conceptual-priority order
(see §4). Phases 1 and 2 are each split into independently-plannable units.

- **Phase 0 — Foundation.** Fork + pin Frida; stand up the custom build; reproduce a
  vanilla `compile_script` → `create_script_from_bytes` round-trip on the custom build.
  *Done when:* a hello-world agent compiles to bytecode and runs on the custom Frida.
- **Phase 1a — L4 (JS obfuscation, build-tooling only).** Independent of the fork; can ship
  first. Insert the obfuscation step ahead of bytecode compilation. *Done when:* real
  identifier names and string literals are absent from the produced bytecode.
- **Phase 1b — L3 (QuickJS fork: opcode permutation + blob encryption + GumJS decrypt
  hook).** *Done when:* (a) a stock QuickJS `2024-01-13` disassembler fails on the protected
  blob; (b) the protected agent runs correctly on the custom Frida; (c) the blob is
  decrypted only in memory at load.
- **Phase 2a — L1 Frida-side scaffolding.** The native-module loading path, GumJS glue, and
  the per-OS obfuscation toolchain + static-link-into-binary build. No dependency on the
  owner's logic inventory. *Done when:* an obfuscated stub native core links into the custom
  Frida, is invoked from a JS shim, and exposes no distinct module to
  `Module.enumerateModules`.
- **Scoping gate (answers §10).** Before Phase 2b the owner **inventories the agent** and
  names which functions move to native. Phase 2b cannot be sized until this is done.
- **Phase 2b — L1 logic port (chief lever).** Port the named logic to obfuscated C.
  *Done when:* the named sensitive logic is absent from the JS bytecode and the agent
  behaves identically.
- **Phase 3 — L2 (apex, deep VM).** Deep opcode virtualization for the JS that remains; it
  supersedes L3's permutation in the fork (see the L2 composition note). *Done when:* the
  deep VM is in place, the agent runs correctly, and the Phase-2/3 white-box red-team
  (below) fails to recover VM semantics within its time-box.
- **Phase 4 — L5 (+ L6 if in scope).** Light anti-tamper in the native core. *Done when:*
  integrity + anti-debug checks are present and pass functional tests; if L6 is in scope it
  is embedded-key by default (server-tethered is a separate spec — §7) and *done when* keys
  never appear in cleartext except at point of use; if L6 is out of scope, this sub-part is
  a documented no-op.

**Two-tier validation — the bar matches what the layer claims:**

- **Phases 0 / 1a / 1b — standard-tooling bar.** Functional correctness on the custom Frida;
  measured runtime/size overhead within an agreed budget; a red-team with *off-the-shelf*
  QuickJS tooling confirms the disassembler/decompiler barrier.
- **Phases 2 / 3 — white-box bar** (matches §2). A time-boxed red-team that actually
  exercises the §2 attacker: patching the custom binary, reversing the dispatch loop /
  lifting the VM, and dumping RAM at runtime. Pass = the named reviewer cannot recover the
  protected logic within the agreed budget — this is where §1's "weeks, not minutes" becomes
  a concrete, measured criterion. A standard-tooling red-team is **not** sufficient to
  validate Phase 2 or 3.

---

## 10. Open questions & assumptions

- **ASSUMPTION (key unknown):** the agent's logic size/shape is not yet specified. The
  feasibility and payoff of L1 (native extraction) — the strongest layer — depends
  entirely on this. This spec parameterizes the native boundary; the owner must identify
  which functions move to native. *If most logic cannot be nativized, the achievable
  ceiling drops to L2–L4 (VM + permute + encrypt + obfuscate), which is weaker in
  white-box.*
- **L2 VM depth (recommended: deep).** Deep re-encoding is the target for "strongest";
  shallow is the fallback only if deep proves infeasible (see §5 L2). Owner to confirm
  before Phase 3.
- Which of Linux / Windows / macOS are hard requirements (affects toolchain scope and
  whether a portable design is needed).
- Are there cryptographic keys/secrets in the agent (decides whether L6 is in scope)?
- Acceptable performance and artifact-size overhead (VM + OLLVM both add runtime cost).
- Offline vs online distribution (decides embedded vs server-tethered key model).

---

## 11. Honest summary of residual risk

Even with all layers, an attacker who holds the custom binary and controls the machine can,
given enough expert time: dump decrypted bytecode/objects from RAM, recover the opcode
permutation and keys from the binary, lift the VM, and reverse the (obfuscated) native
core. This design pushes that cost to the level of defeating a commercial protector — the
practical meaning of "strongest" here. The durable strength comes from **L1 (native) and
L2 (VM)**; L3/L4 are cheap baselines; L5 is nuisance-only; L6 is conditional.
