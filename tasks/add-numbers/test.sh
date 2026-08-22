#!/usr/bin/env bash
set -euo pipefail

# Verify solution.py exists
test -f solution.py || { echo "FAIL: solution.py not found"; exit 1; }

# Verify the function works
python3 -c "
from solution import add
assert add(2, 3) == 5, f'Expected 5, got {add(2, 3)}'
assert add(-1, 1) == 0, f'Expected 0, got {add(-1, 1)}'
assert add(0, 0) == 0, f'Expected 0, got {add(0, 0)}'
assert add(100, 200) == 300, f'Expected 300, got {add(100, 200)}'
print('ALL TESTS PASSED')
"
