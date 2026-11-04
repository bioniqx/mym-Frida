#!/usr/bin/env python3
"""Deterministically permute the safe subset of QuickJS DEF(...) opcode
ordering in the fork's quickjs-opcode.h. Opcodes reached by arithmetic
offset or range comparison in quickjs.c (see CONSTRAINED_OPCODES) keep
their original slot; only the remaining opcodes are shuffled."""
import argparse
import random
import re
import shutil
import tempfile
from pathlib import Path

DEF_RE = re.compile(r'^\s*DEF\(\s*([A-Za-z0-9_]+)\s*,')

# Bare DEF(...) identifiers (no "OP_" prefix) that quickjs.c reaches by
# arithmetic offset or range comparison against the OP_* enum. Found via
# `grep -nE 'OP_[a-z0-9_]+ *[-+]' quickjs.c` and
# `grep -nE '(>=|<=|<|>) *OP_' quickjs.c` in the fork checkout (Steps 3-4),
# extended with every name the grep review of the fork checkout at
# cd41bdbf found (Step 10), plus the unnamed adjacency partners those
# arithmetic mappings require (e.g. `OP_get_arg + is_put` needs put_arg to
# stay get_arg's immediate successor; get_with_scope_opcode() needs the
# whole with_* family consecutive; `OP_if_false8 + (op - OP_if_false)`
# needs if_false/if_true/goto consecutive; `OP_dec + (op - OP_post_dec)`
# needs dec/inc and post_dec/post_inc consecutive).
# Names below that live inside the #if SHORT_OPCODES region (push_0,
# if_false8, *_0 families, call0, ...) are additionally held structurally
# by position in apply_permutation(). The scope_* temps are lowercase
# def(...) lines, never matched by DEF_RE, and are listed only to mirror
# the grep record.
CONSTRAINED_OPCODES = {
    # plan starter list
    "get_loc0", "get_loc1", "get_loc2", "get_loc3",
    "put_loc0", "put_loc1", "put_loc2", "put_loc3",
    "get_arg0", "get_arg1", "get_arg2", "get_arg3",
    "push_i32",
    # quickjs.c hardcodes `op == 0` as "no/invalid opcode" (e.g. in
    # compute_stack_size), so invalid must keep enum value 0
    "invalid",
    # OP_TEMP_START = OP_nop + 1: nop must stay the last non-short,
    # non-temporary opcode
    "nop",
    # OP_push_const8 + op - OP_push_const maps push_const -> push_const8
    # and fclosure -> fclosure8, so fclosure must stay push_const + 1
    "push_const", "fclosure",
    # OP_get_arg + is_put -> put_arg must remain get_arg + 1
    "get_arg", "put_arg",
    # Peephole rewrites use op +/- 1 across the long get/put/set variable
    # families (optimize_scope_make_ref's `get_op + 1`; `cc.op + 1`,
    # `op - 1`, `op + 1` in resolve_labels), so each triple must stay
    # consecutive and ordered: get_x, put_x = get_x + 1, set_x = put_x + 1.
    "get_loc", "put_loc", "set_loc",
    "get_loc_check", "put_loc_check", "set_loc_check",
    "set_arg",
    "get_var_ref", "put_var_ref", "set_var_ref",
    # optimize_scope_make_ref resolves lexical closure refs via
    # get_op = OP_get_var_ref_check and emits `bc_buf[pos] = get_op + 1`,
    # so put_var_ref_check must stay get_var_ref_check + 1 (the header's
    # own "must come after get_var_ref_check" comment at cd41bdbf).
    # Missed by the original grep review; found by review r1-2.
    "get_var_ref_check", "put_var_ref_check",
    # OP_get_var_undef + (op - OP_scope_get_var_undef) and the
    # interpreter's `opcode - OP_get_var_undef` flag
    "get_var_undef", "get_var", "put_var",
    # get_with_scope_opcode(): OP_with_get_var + (op - OP_scope_get_var)
    # walks the whole family
    "with_get_var", "with_put_var", "with_delete_var", "with_make_ref",
    "with_get_ref",
    # OP_if_false8 + (op - OP_if_false) for if_false/if_true/goto
    "if_false", "if_true", "goto",
    # OP_dec + (op - OP_post_dec) and op - OP_post_dec + OP_dec
    "dec", "inc", "post_dec", "post_inc",
    # opcode += OP_define_method - OP_define_method_computed
    "define_method", "define_method_computed",
    # resolve_labels' tail-call transform emits `op + 1` for call and
    # call_method, so tail_call must stay call + 1 and tail_call_method
    # must stay call_method + 1
    "call", "tail_call", "call_method", "tail_call_method",
    # short-opcode anchors named by the greps; held by position anyway
    "push_0", "push_const8", "if_false8", "set_loc0", "put_arg0", "set_arg0",
    "get_var_ref0", "put_var_ref0", "set_var_ref0", "call0",
    # lowercase def(...) temps named by the greps (never permuted)
    "scope_get_var", "scope_get_var_undef",
}


# quickjs.c consumes some constrained opcodes through their canonical
# successor: optimize_scope_make_ref receives get_op =
# OP_get_var_ref_check for lexical closure refs and emits
# `bc_buf[pos] = get_op + 1`, and the resolve_labels/peephole passes walk
# the long get/put/set families with `cc.op + 1` / `op - 1`. In the
# fork's quickjs-opcode.h each pair below is a consecutive DEF(...) run
# guarded by a "must come after" comment. For every pair that is
# canonically adjacent in the header and has at least one member held by
# CONSTRAINED_OPCODES, apply_permutation() refuses to emit a header in
# which the pair is no longer adjacent -- so the r1-2 gap class (one
# half of a pair constrained while its canonical successor is left free
# to shuffle) can never slip through silently again. Family-external
# neighbors (set_loc_check -> put_loc_check_init,
# put_var_ref_check -> put_var_ref_check_init) are deliberately not
# listed: the review confirms they are referenced only by name and need
# no constraint.
PROTECTED_ADJACENT_PAIRS = [
    ("get_loc", "put_loc"),
    ("put_loc", "set_loc"),
    ("get_arg", "put_arg"),
    ("put_arg", "set_arg"),
    ("get_var_ref", "put_var_ref"),
    ("put_var_ref", "set_var_ref"),
    ("get_loc_check", "put_loc_check"),
    ("put_loc_check", "set_loc_check"),
    ("get_var_ref_check", "put_var_ref_check"),
]


def find_separated_protected_pairs(ids, new_ids, constrained):
    """Return the protected get/put/set pairs that are canonically
    adjacent (consecutive entries of ids) but no longer sit on adjacent
    slots in new_ids. A non-empty result means the emitted header would
    make quickjs.c apply its `get_op + 1`-style rewrites to unrelated
    opcodes: either CONSTRAINED_OPCODES holds one half of a pair while
    its canonical successor was left free to shuffle, or the permutation
    logic broke its hold-constrained-opcodes invariant."""
    slot = {oid: i for i, oid in enumerate(new_ids)}
    protected = set(PROTECTED_ADJACENT_PAIRS)
    separated = []
    for before, after in zip(ids, ids[1:]):
        if ((before, after) in protected
                and (before in constrained or after in constrained)):
            if slot[after] != slot[before] + 1:
                separated.append((before, after))
    return separated


def parse_def_lines(text):
    """Return (lines, defs) where defs is [(line_index, opcode_id), ...]
    for every DEF(...) line, in file order."""
    lines = text.splitlines(keepends=True)
    defs = [(i, DEF_RE.match(l).group(1)) for i, l in enumerate(lines) if DEF_RE.match(l)]
    return lines, defs


def def_entry_spans(lines, defs):
    """Return {line_index: n_lines} for each DEF entry. An entry owns its
    line plus any continuation lines of its trailing block comment (e.g.
    DEF(regexp, ...) has a two-line comment)."""
    spans = {}
    for idx, _oid in defs:
        n = 1
        text = lines[idx]
        while text.count("/*") > text.count("*/"):
            n += 1
            text += lines[idx + n - 1]
        spans[idx] = n
    return spans


def find_short_opcode_start(lines):
    for i, line in enumerate(lines):
        # The fork guards the region with `#if SHORT_OPCODES` (not `#ifdef`),
        # so match any #if-style directive naming SHORT_OPCODES.
        if line.strip().startswith('#if') and 'SHORT_OPCODES' in line:
            return i
    return None


def generate_permutation(opcode_ids, seed_hex, constrained):
    """Return a reordering of opcode_ids: ids in `constrained` keep their
    original slot; the rest are shuffled deterministically from seed_hex."""
    rng = random.Random(int(seed_hex, 16))
    safe_slots = [i for i, oid in enumerate(opcode_ids) if oid not in constrained]
    shuffled = [opcode_ids[i] for i in safe_slots]
    rng.shuffle(shuffled)
    result = list(opcode_ids)
    for slot, oid in zip(safe_slots, shuffled):
        result[slot] = oid
    return result


def apply_permutation(quickjs_dir, seed_hex, constrained_names=None):
    quickjs_dir = Path(quickjs_dir)
    header = quickjs_dir / "quickjs-opcode.h"
    canonical = quickjs_dir / "quickjs-opcode.h.canonical"
    if not canonical.exists():
        shutil.copyfile(header, canonical)
    lines, defs = parse_def_lines(canonical.read_text())
    short_start = find_short_opcode_start(lines)
    if constrained_names is None:
        constrained_names = CONSTRAINED_OPCODES
    constrained = set(constrained_names)
    if short_start is not None:
        constrained |= {oid for idx, oid in defs if idx > short_start}
    ids = [oid for _, oid in defs]
    new_ids = generate_permutation(ids, seed_hex, constrained)
    # Fail loudly before any write: a header that separates a protected
    # pair would make quickjs.c rewrite bytecode with unrelated opcodes
    # (silent miscompilation), so neither quickjs-opcode.h nor its saved
    # .canonical copy is touched when the guard trips.
    separated = find_separated_protected_pairs(ids, new_ids, constrained)
    if separated:
        detail = ", ".join(f"({a}, {b})" for a, b in separated)
        raise SystemExit(
            "ERROR: this seed separates canonically adjacent opcode pairs "
            "that quickjs.c consumes by arithmetic offset (e.g. "
            f"`get_op + 1` in optimize_scope_make_ref): {detail}. Add the "
            "missing partners to CONSTRAINED_OPCODES; quickjs-opcode.h "
            "was left unchanged."
        )
    # Move each whole DEF(...) entry (identifier AND its size/n_pop/n_push/
    # fmt arguments, plus any trailing comment including continuation
    # lines) to the new slot. Swapping only the identifier would leave each
    # slot's opcode metadata behind, giving renamed opcodes the stack
    # effects of the opcode whose enum value they took over, which corrupts
    # every table derived from the header (opcode_info[]) and breaks the
    # compiler.
    spans = def_entry_spans(lines, defs)
    entry_by_id = {oid: lines[idx: idx + spans[idx]] for idx, oid in defs}
    out = []
    i = 0
    next_def = iter(zip(defs, new_ids))
    pending = next(next_def, None)
    while i < len(lines):
        if pending is not None and i == pending[0][0]:
            (idx, _old_id), new_id = pending
            out.extend(entry_by_id[new_id])
            i += spans[idx]
            pending = next(next_def, None)
        else:
            out.append(lines[i])
            i += 1
    header.write_text("".join(out))
    moved = sum(1 for old, new in zip(ids, new_ids) if old != new)
    print(f"permuted {len(defs)} opcodes, {moved} moved, {len(constrained)} held fixed -> {header}")


# Seed chosen so that in the gap scenario below (only get_var_ref_check
# constrained, its canonical successor left free) the successor actually
# moves away from its canonical slot, tripping the guard deterministically.
GUARD_GAP_SEED = "deadbeef"


def self_test():
    ids = ["a", "get_loc0", "b", "c", "get_arg1", "d", "e"]
    constrained = {"get_loc0", "get_arg1"}
    permuted = generate_permutation(ids, "deadbeef", constrained)
    assert sorted(permuted) == sorted(ids), "not a bijection"
    assert permuted[1] == "get_loc0", "constrained opcode moved"
    assert permuted[4] == "get_arg1", "constrained opcode moved"
    assert permuted == generate_permutation(ids, "deadbeef", constrained), "not deterministic for same seed"
    assert permuted != generate_permutation(ids, "cafef00d", constrained), "seed had no effect"
    # r1-2 guardrail: every canonically adjacent get/put/set family pair
    # with a constrained member must stay adjacent in the permutation, and
    # the tool must fail loudly when a permutation would separate one --
    # the exact gap that let get_var_ref_check/put_var_ref_check drift
    # apart on essentially every seed (r1-2 blocker).
    pair_ids = ["x1", "get_var_ref_check", "put_var_ref_check", "x2", "x3"]
    full = {"get_var_ref_check", "put_var_ref_check"}
    assert find_separated_protected_pairs(
        pair_ids, generate_permutation(pair_ids, "deadbeef", full), full
    ) == [], "protected pair separated although both members are constrained"
    gap = {"get_var_ref_check"}  # successor forgotten: the r1-2 gap class
    assert find_separated_protected_pairs(
        pair_ids, generate_permutation(pair_ids, GUARD_GAP_SEED, gap), gap
    ) == [("get_var_ref_check", "put_var_ref_check")], \
        "guard did not flag the separated get_var_ref_check/put_var_ref_check pair"
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        header = d / "quickjs-opcode.h"
        original = (
            "DEF(x0, 1, 0, 0, none)\n"
            "DEF(get_var_ref_check, 3, 0, 1, var_ref)\n"
            "DEF(put_var_ref_check, 3, 1, 0, var_ref) /* must come after get_var_ref_check */\n"
            "DEF(x1, 1, 0, 0, none)\n"
            "DEF(x2, 1, 0, 0, none)\n"
            "DEF(x3, 1, 0, 0, none)\n"
        )
        header.write_text(original)
        try:
            apply_permutation(d, GUARD_GAP_SEED, constrained_names=gap)
        except SystemExit as e:
            assert "get_var_ref_check" in str(e) and "put_var_ref_check" in str(e), \
                f"loud-failure message does not name the pair: {e}"
        else:
            raise AssertionError("tool emitted a header that separates a protected pair")
        assert header.read_text() == original, "failed run modified quickjs-opcode.h"
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

    apply_permutation(args.quickjs, args.seed)


if __name__ == "__main__":
    main()
