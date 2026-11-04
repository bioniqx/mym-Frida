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
