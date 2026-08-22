#!/usr/bin/env bash
set -euo pipefail

# Verify solution.py exists
test -f solution.py || { echo "FAIL: solution.py not found"; exit 1; }

# Verify the function works
python3 -c "
from solution import sort_list
assert sort_list([3, 1, 4, 1, 5]) == [1, 1, 3, 4, 5]
assert sort_list([]) == []
assert sort_list(['b', 'a', 'c']) == ['a', 'b', 'c']
assert sort_list([1]) == [1]
assert sort_list([5, 4, 3, 2, 1]) == [1, 2, 3, 4, 5]
print('ALL TESTS PASSED')
"
