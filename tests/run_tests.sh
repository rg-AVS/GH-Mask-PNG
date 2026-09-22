#!/bin/sh
# run_tests.sh -- every check, in dependency order.
#
#   make test        (or)   ./tests/run_tests.sh
#
# The Python checks need no build and no display; the C++ one is skipped if
# build/ is empty, so this passes on a machine that has never run make.
cd "$(dirname "$0")/.."
fail=0

say()  { printf '\n=== %s ===\n' "$1"; }
pass() { printf '  PASS  %s\n' "$1"; }
bad()  { printf '  FAIL  %s\n' "$1"; fail=1; }

say "The converter (pure Python, no build needed)"
python3 tests/test_maskmaker.py >/dev/null 2>&1 && pass "gui/maskmaker.py" || bad "gui/maskmaker.py"

say "The window (against a stand-in tkinter)"
python3 tests/test_gui.py >/dev/null 2>&1 && pass "gui/mask_gui.py" || bad "gui/mask_gui.py"

say "The C++ tool"
if [ ! -x build/png2mask ]; then
  printf '  SKIP  build/png2mask (not built; run make)\n'
else
  TMP=$(mktemp -d)
  trap 'rm -rf "$TMP"' EXIT
  if build/png2mask "testset/Shapes/PNG to MAsk.png" "$TMP/a.xml" >/dev/null 2>&1
    then pass "converts artwork"; else bad "could not convert artwork"; fi
  if build/png2mask "Ref/Star for Mask.png" "$TMP/b.xml" >/dev/null 2>&1
    then pass "converts a traced star"; else bad "could not convert the star"; fi
  # A PNG with no alpha must be refused, not guessed at.
  if build/png2mask "$TMP/a.xml" "$TMP/c.xml" >/dev/null 2>&1
    then bad "accepted a file that is not a PNG"; else pass "refuses a non-PNG"; fi
fi

printf '\n'
if [ $fail -eq 0 ]; then echo "ALL TESTS PASSED"; exit 0; fi
echo "TESTS FAILED"; exit 1
