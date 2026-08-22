#!/usr/bin/env bash
set -euo pipefail

# Verify greeting.txt exists
test -f greeting.txt || { echo "FAIL: greeting.txt not found"; exit 1; }

# Verify content
content=$(cat greeting.txt)
if [[ "$content" != "Hello, World!" ]]; then
  echo "FAIL: expected 'Hello, World!' but got '$content'"
  exit 1
fi

echo "ALL TESTS PASSED"
