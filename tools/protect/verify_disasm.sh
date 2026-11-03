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
