#!/bin/sh
# Clean-room test for the riscv-spec skill's bundled script.
#
# Runs INSIDE a container with the skill mounted at /skill. It assumes nothing
# else exists: no UDB clone, no cache, no network unless the caller provides it.
# Set OFFLINE=1 to assert the offline degradation path instead of the fetch path.
#
# Every check asserts a specific user-visible behaviour, not just an exit code,
# because a script that exits 0 while printing a Python traceback is still broken.

set -u
S="python3 /skill/scripts/riscv_docs.py"
CACHE="${RISCV_SPEC_CACHE:-/tmp/rs-cache}"
export RISCV_SPEC_CACHE="$CACHE"
PASS=0
FAIL=0
OUT=/tmp/out.$$

ok()   { PASS=$((PASS + 1)); echo "  PASS  $1"; }
bad()  { FAIL=$((FAIL + 1)); echo "  FAIL  $1"; sed 's/^/          /' "$OUT" | head -6; }

# run <name> <expect-exit 0|nonzero> <must-contain> -- <cmd...>
run() {
  name="$1"; want="$2"; needle="$3"; shift 4
  "$@" >"$OUT" 2>&1
  rc=$?
  if [ "$want" = "0" ] && [ "$rc" -ne 0 ]; then bad "$name (exit $rc, wanted 0)"; return; fi
  if [ "$want" = "nonzero" ] && [ "$rc" -eq 0 ]; then bad "$name (exit 0, wanted failure)"; return; fi
  if grep -q "Traceback (most recent call last)" "$OUT"; then bad "$name (python traceback leaked)"; return; fi
  if [ -n "$needle" ] && ! grep -qi -- "$needle" "$OUT"; then bad "$name (missing '$needle')"; return; fi
  ok "$name"
}

echo "python: $(python3 --version 2>&1)   offline: ${OFFLINE:-0}   cache: $CACHE"
echo

echo "-- static checks"
# Parse rather than py_compile: py_compile writes __pycache__, which fails on a
# read-only install. Running the script needs no write, and that is the point.
run "script parses"            0 "SYNTAX_OK"  -- python3 -c "import ast;ast.parse(open('/skill/scripts/riscv_docs.py').read());print('SYNTAX_OK')"
run "manifest is valid json"   0 "docs.riscv.org" -- python3 -c "import json;print(json.load(open('/skill/references/sources.json'))['base_url'])"
run "runs from read-only mount" 0 "sbi"       -- $S list
run "help works"               0 "usage"       -- $S --help

# A chapter link is relative to its own page, not to the spec version root. The
# ISA manual is the only spec published in subdirectories, so it is the only one
# that 404s when this is wrong.
run "chapter link resolves"    0 "LINKS_OK"  -- python3 -c "
import sys; sys.path.insert(0, '/skill/scripts')
from riscv_docs import resolve_page as r
assert r('unpriv/unpriv-index.html', 'rv64.html') == 'unpriv/rv64.html'
assert r('unpriv/unpriv-index.html', '../priv/machine.html') == 'priv/machine.html'
assert r('index.html', 'chapter.html') == 'chapter.html'
assert r('unpriv/unpriv-index.html', '../../../home/index.html') is None
assert r('index.html', '../escape.html') is None
print('LINKS_OK')"

echo "-- offline-safe commands (no network needed)"
run "list runs"                0 "sbi"         -- $S list
run "list marks uncached"      0 "not cached"  -- $S list
run "status on empty cache"    0 "empty"       -- $S status
run "search on empty cache"    nonzero "cache is empty" -- $S search anything
run "unknown slug is clean"    nonzero "unknown spec"   -- $S fetch definitely-not-a-spec

if [ "${OFFLINE:-0}" = "1" ]; then
  echo "-- offline degradation"
  run "versions fails clean"   0 "ERROR"       -- $S versions sbi
  run "fetch fails clean"      nonzero ""      -- $S fetch sbi --limit 1
else
  echo "-- network path"
  run "versions finds v3.0"    0 "v3.0"        -- $S versions sbi
  run "fetch caches pages"     0 "cached"      -- $S fetch sbi --limit 3
  run "status shows sbi"       0 "sbi"         -- $S status
  # Search only what --limit actually fetched. --limit walks the spec's own nav
  # order, which begins with front matter, so do not assert on chapter prose here.
  run "search finds text"      0 "docs.riscv.org" -- $S search "RISC-V"
  run "cite url is versioned"  0 "/sbi/v3.0/"  -- $S search "RISC-V"

  echo "-- staleness detection"
  python3 - <<'PY' >/dev/null 2>&1
import json, os, pathlib
c = pathlib.Path(os.environ["RISCV_SPEC_CACHE"]) / "sbi" / "meta.json"
if c.exists():
    m = json.loads(c.read_text()); m["version"] = "v0.1"; c.write_text(json.dumps(m))
PY
  run "detects stale cache"    0 "STALE"       -- $S versions sbi
fi

rm -f "$OUT"
echo
echo "RESULT pass=$PASS fail=$FAIL"
[ "$FAIL" -eq 0 ]
