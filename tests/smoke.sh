#!/usr/bin/env bash
# Smoke test — catches the runtime/integration bugs that "looks-correct" code hides.
# Local, gitignored. Run before claiming any schema/SQL change is done.
#
#   ./tests/smoke.sh            compile + apply compat views + analyse_all   (~20s)
#   ./tests/smoke.sh --full     also compute_all                            (slow)
#   ./tests/smoke.sh --import   also import_all --update (writes to health.db)
#
# Exit 0 = pipeline runs clean. Non-zero = something is broken.

set -uo pipefail
cd "$(dirname "$0")/.."

PY=".venv/bin/python"
[ -x "$PY" ] || PY="python3"
FAIL=0

step() { printf '\n\033[1m== %s ==\033[0m\n' "$1"; }
ok()   { printf '  \033[32m✓\033[0m %s\n' "$1"; }
bad()  { printf '  \033[31m✗\033[0m %s\n' "$1"; FAIL=1; }

step "1. Compile all scripts (catches SyntaxError without running)"
if "$PY" -m compileall -q scripts/; then ok "all scripts compile"; else bad "compile failed"; fi

step "2. DB exists"
if [ -f data/health.db ]; then ok "data/health.db present"; else bad "data/health.db missing — run init_db.py + import first"; fi

step "3. Apply v1->v2 compat views (idempotent)"
if "$PY" scripts/utils/compat_views.py; then ok "compat views applied"; else bad "compat_views.py failed"; fi

step "4. SQL table/view references (advisory — heuristic, may report prose/runtime tables)"
"$PY" - <<'PYEOF'
import re, sys
from pathlib import Path
sys.path.insert(0, "scripts")
from modules.db import open_db
con = open_db()
real = {r[0] for r in con.execute(
    "SELECT name FROM sqlite_master WHERE type IN('table','view')")}
PYMOD = {"pathlib","collections","datetime","os","sys","typing","health_config",
         "utils","argparse","json","math","re","itertools","functools",
         "subprocess","time","statistics","dataclasses","__future__","concurrent"}
pat  = re.compile(r'\b(?:FROM|JOIN)\s+([a-z_][a-z0-9_]*)', re.I)
ctep = re.compile(r'\b([a-z_][a-z0-9_]*)\s+AS\s*\(', re.I)
missing = {}
for f in Path("scripts").rglob("*.py"):
    src = f.read_text(encoding="utf-8", errors="replace")
    ctes = {m.lower() for m in ctep.findall(src)}
    for line in src.splitlines():
        if "import" in line:
            continue
        for t in pat.findall(line):
            tl = t.lower()
            if tl in real or tl in ctes or tl in PYMOD:
                continue
            missing.setdefault(tl, set()).add(f.name)
# Filter obvious English-prose / alias noise: require name to look table-ish
NOISE = {"the","a","an","this","what","or","and","open","list","ts","timestamp",
         "iso","yyyy","median","pdf","raw","scratch","l","e","exc","few","hat",
         "any","repo","inside","photo","barcode","obf","structured","environment",
         "successive","waveform","starttime","pre","lux","timestamps","dicts",
         "philips","arrhythmian","laborbefand","your","sourcename","account",
         "fitness","identity","physicalinformation","ha","llm","timeline","sqlite_master"}
missing = {k:v for k,v in missing.items() if k not in NOISE}
if missing:
    print("  ADVISORY — names not found as table/view (verify; many are prose or runtime-created):")
    for t in sorted(missing):
        print(f"    {t:28} <- {', '.join(sorted(list(missing[t]))[:4])}")
else:
    print("  all FROM/JOIN names resolve")
PYEOF
if [ $? -eq 0 ]; then
  ok "reference scan done (findings above are advisory only — real gate is the pipeline below)"
else
  bad "reference scan crashed — that's a bug in the scan itself, not an advisory finding"
fi

step "4b. SQL column references (hard gate — exact, not heuristic)"
# Ergaenzt Schritt 4: der prueft Tabellennamen heuristisch und ist deshalb nur
# beratend. Dieser hier vergleicht die SELECT-Spaltenlisten exakt gegen
# PRAGMA table_info und ueberspringt alles, was er nicht sicher zerlegen kann --
# also kein Rauschen, jeder Treffer ist ein echter Laufzeitfehler.
if "$PY" scripts/check_sql_columns.py --quiet; then
  ok "all selected columns exist"
else
  bad "SELECT queries reference non-existent columns (see above)"
fi

DO_FULL=0
DO_IMPORT=0
for arg in "$@"; do
  [ "$arg" = "--full" ] && DO_FULL=1
  [ "$arg" = "--import" ] && DO_IMPORT=1
done

# Importer errors caused by missing OAuth/API credentials (Oura, Polar
# AccessLink, Garmin), missing optional export files (Apple Health XML,
# HomeAssistant config) or an unreachable weather API are expected on a
# fresh checkout and don't indicate a code bug — only fail on anything else.
KNOWN_ACCEPTABLE_IMPORT_FAILURES="import_apple.py import_homeassistant.py import_oura.py import_polar_accesslink.py import_cgm.py garmin_download.py import_garmin.py import_dwd_brightsky.py import_kiste_export.py"

if [ "$DO_IMPORT" -eq 1 ]; then
  step "5. import_all --update (writes to health.db; only fails on unexpected importer errors)"
  OUT=$("$PY" scripts/import_all.py --update 2>&1)
  FAILED_LINE=$(echo "$OUT" | grep -oE '[0-9]+ Importer mit Fehlern: .*' | tail -1)
  if [ -z "$FAILED_LINE" ]; then
    ok "no importer failures"
  else
    FAILED_LIST=${FAILED_LINE#*: }
    UNEXPECTED=""
    IFS=',' read -ra ARR <<< "$FAILED_LIST"
    for s in "${ARR[@]}"; do
      s=$(echo "$s" | xargs)  # trim whitespace
      [ -z "$s" ] && continue
      case " $KNOWN_ACCEPTABLE_IMPORT_FAILURES " in
        *" $s "*) ;;
        *) UNEXPECTED="$UNEXPECTED $s" ;;
      esac
    done
    if [ -n "$UNEXPECTED" ]; then
      bad "unexpected importer failure(s):$UNEXPECTED"
    else
      ok "only known/expected importer failures (missing credentials/optional files): $FAILED_LIST"
    fi
  fi
fi

if [ "$DO_FULL" -eq 1 ]; then
  step "6. compute_all (recomputes derived tables — slow)"
  if "$PY" scripts/compute_all.py >/tmp/kyoro_compute.log 2>&1; then
    ok "compute_all clean"
  else
    bad "compute_all failed"; tail -15 /tmp/kyoro_compute.log
  fi
fi

step "7. analyse_all (all analysis scripts)"
OUT=$("$PY" scripts/analyse_all.py 2>&1)
echo "$OUT" | grep -iE "Ausgeführt:|Ran:" | sed 's/^/  /'
if echo "$OUT" | grep -qiE "Fehler: 0|Errors: 0"; then
  ok "analyse_all: 0 errors"
else
  bad "analyse_all had failures"; echo "$OUT" | grep -iE "Fehlgeschlagen|Failed" | sed 's/^/  /'
fi

step "8. Unit tests (pure logic — no personal data touched, e.g. config-path and inbox-sniffing regressions)"
# Always "$PY -m pytest", never the bare pytest console-script: -m explicitly
# puts the repo root on sys.path, which tests that do
# "from scripts.modules... import ..." (implicit namespace package, no
# scripts/__init__.py) rely on. The bare entry-point script doesn't add it
# the same way and fails collection with "No module named 'scripts'" even
# when it resolves to this project's own .venv/bin/pytest.
PYTEST="$PY -m pytest"
if $PYTEST tests/unit -q; then
  ok "pytest tests/unit clean"
else
  bad "pytest tests/unit had failures"
fi

echo
if [ "$FAIL" -eq 0 ]; then
  printf '\033[32mSMOKE OK\033[0m\n'; exit 0
else
  printf '\033[31mSMOKE FAILED\033[0m\n'; exit 1
fi
