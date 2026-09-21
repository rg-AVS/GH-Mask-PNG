#!/bin/sh
# check_testset.sh -- renders every <Mask> in a test set back to pixels and
# compares it against the PNG it was generated from. Proves the set is
# internally consistent before it goes anywhere near Hippotizer, so a
# mismatch over there is a real finding about Hippotizer and not a bug here.
#
#   ./tests/check_testset.sh testset
set -e
cd "$(dirname "$0")/.."
DIR=${1:-testset}
BUILD=build
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
fail=0

for png in "$DIR"/*.png; do
  name=$(basename "$png" .png)
  res=$(echo "$name" | cut -d_ -f2)
  map=$(echo "$name" | cut -d_ -f3)
  idx=$(echo "${name%%_*}" | sed 's/^0*//')   # 01 -> 1, to match index="1"
  $BUILD/mask2png "$DIR/Masks.xml" "$TMP" --mask "$idx" --res "$res" --map "$map" >/dev/null
  if $BUILD/mask_diff "$png" "$TMP/$name.png" >/dev/null; then
    printf '  PASS  %s  (%s, %s)\n' "$name" "$res" "$map"
  else
    printf '  FAIL  %s  ' "$name"
    $BUILD/mask_diff "$png" "$TMP/$name.png" | head -1
    fail=1
  fi
done
exit $fail
