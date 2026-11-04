#!/bin/sh
# roundtrip.sh — subcommand adapter over tools/harness/roundtrip.py.
#
# verify_disasm.sh (T06) expects a tool with two subcommands:
#   roundtrip.sh compile <source.js> <out.bin>
#       Compile source.js with the custom Frida build and write the raw
#       serialized bytecode to out.bin.
#   roundtrip.sh run <blob.bin>
#       Load the bytecode back under the custom Frida build and print the
#       agent's marker (ROUNDTRIP_OK on success).
#
# The heavy lifting lives in tools/harness/roundtrip.py (T02): its compile()
# and run() attach to a local process using this worktree's built `frida`
# module. frida_env.sh (C6) exports the PYTHONPATH that makes that module
# importable; tools/harness is prepended so `import roundtrip` resolves.

set -eu

usage() {
    echo "usage: $0 compile <source.js> <out.bin>" >&2
    echo "       $0 run <blob.bin>" >&2
}

if [ "$#" -lt 1 ]; then
    usage
    exit 2
fi

SELF_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
SRC_ROOT=$(CDPATH='' cd -- "$SELF_DIR/../.." && pwd)

. "$SRC_ROOT/tools/protect/frida_env.sh"

PYTHONPATH="$SRC_ROOT/tools/harness${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONPATH

case "$1" in
compile)
    if [ "$#" -ne 3 ]; then
        usage
        exit 2
    fi
    python3 - "$2" "$3" <<'PYEOF'
import sys

import roundtrip

source_path, out_path = sys.argv[1], sys.argv[2]
bytecode = roundtrip.compile(source_path)
with open(out_path, "wb") as f:
    f.write(bytecode)
print("COMPILED %d bytes -> %s" % (len(bytecode), out_path))
PYEOF
    ;;
run)
    if [ "$#" -ne 2 ]; then
        usage
        exit 2
    fi
    python3 - "$2" <<'PYEOF'
import sys

import roundtrip

with open(sys.argv[1], "rb") as f:
    bytecode = f.read()
print(roundtrip.run(bytecode))
PYEOF
    ;;
*)
    usage
    exit 2
    ;;
esac
