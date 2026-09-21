#!/bin/sh
# run_tests.sh -- the self-checks, in dependency order. No test framework:
# each check is a tool this project already ships, run against the sample
# files, with its exit code as the assertion.
#
#   make test        (or)   ./tests/run_tests.sh
cd "$(dirname "$0")/.."
BUILD=build
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
fail=0

say()  { printf '\n=== %s ===\n' "$1"; }
pass() { printf '  PASS  %s\n' "$1"; }
bad()  { printf '  FAIL  %s\n' "$1"; fail=1; }

[ -x "$BUILD/png2mask" ] || { echo "build first: make"; exit 1; }

say "XML: parse -> write -> reparse keeps every field"
if $BUILD/xml_roundtrip_check "Mask Data/Masks.xml" >/dev/null 2>&1
  then pass "Mask Data/Masks.xml"; else bad "xml round-trip"; fi
if $BUILD/xml_roundtrip_check testset/Masks.xml >/dev/null 2>&1
  then pass "testset/Masks.xml (9 masks)"; else bad "xml round-trip, test set"; fi

say "PNG: decode -> encode -> decode on an externally-produced file"
if $BUILD/png_roundtrip_check "Ref/Star for Mask.png" "$TMP/rt.png" >/dev/null 2>&1
  then pass "Ref/Star for Mask.png"; else bad "png round-trip"; fi

say "PNG -> mask -> PNG is lossless"
# A hard threshold throws away the source's antialiased edge, so the property
# under test is idempotency: once rendered, a mask survives the trip unchanged.
mkdir -p "$TMP/p1" "$TMP/p2"
$BUILD/png2mask "Ref/Star for Mask.png" "$TMP/a.xml" --simplify 0 --guid-seed 1 >/dev/null &&
$BUILD/mask2png "$TMP/a.xml" "$TMP/p1" --res 1920x1080 >/dev/null &&
$BUILD/png2mask "$TMP/p1/Star_for_Mask.png" "$TMP/b.xml" --simplify 0 --guid-seed 1 >/dev/null &&
$BUILD/mask2png "$TMP/b.xml" "$TMP/p2" --res 1920x1080 >/dev/null
if $BUILD/mask_diff "$TMP/p1/Star_for_Mask.png" "$TMP/p2/Star_for_Mask.png" >/dev/null
  then pass "star traces and re-renders identically"; else bad "star round-trip drifted"; fi

say "Every mapping survives a round-trip at its own resolution"
# Same idempotency property as above, run through each candidate mapping: the
# units differ by a scale factor, so this is where a precision problem in the
# XML writer (or an asymmetry between toUnits and toPixels) would show up.
for map in native stretch fit; do
  mkdir -p "$TMP/$map-1" "$TMP/$map-2"
  $BUILD/png2mask testset/01_1920x1080_native.png "$TMP/$map-a.xml" \
      --map "$map" --simplify 0 --guid-seed 3 >/dev/null &&
  $BUILD/mask2png "$TMP/$map-a.xml" "$TMP/$map-1" --map "$map" --res 1920x1080 >/dev/null &&
  $BUILD/png2mask "$TMP/$map-1/01_1920x1080_native.png" "$TMP/$map-b.xml" \
      --map "$map" --simplify 0 --guid-seed 3 >/dev/null &&
  $BUILD/mask2png "$TMP/$map-b.xml" "$TMP/$map-2" --map "$map" --res 1920x1080 >/dev/null
  if $BUILD/mask_diff "$TMP/$map-1/01_1920x1080_native.png" \
                      "$TMP/$map-2/01_1920x1080_native.png" >/dev/null
    then pass "map=$map"; else bad "map=$map lost pixels"; fi
done

say "Holes survive the trip (the centre square stays cut out)"
$BUILD/png2mask testset/07_1024x768_native.png "$TMP/h.xml" --simplify 0 >/dev/null
rings=$($BUILD/bounds_report "$TMP/h.xml" | grep -c 'shape\[')
if [ "$rings" -eq 3 ]
  then pass "3 rings traced (outer + hole + corner square)"
  else bad "expected 3 rings, traced $rings"; fi

say "Test set is self-consistent (each PNG cancels its own mask)"
./tests/check_testset.sh testset || fail=1

say "The pure-Python converter (no build needed)"
python3 tests/test_maskmaker.py >/dev/null 2>&1 && pass "gui/maskmaker.py" || bad "gui/maskmaker.py"

say "GUI wiring (against a stand-in tkinter)"
python3 tests/test_gui.py >/dev/null 2>&1 && pass "gui/mask_gui.py" || bad "gui/mask_gui.py"

printf '\n'
if [ $fail -eq 0 ]; then echo "ALL TESTS PASSED"; exit 0; fi
echo "TESTS FAILED"; exit 1
