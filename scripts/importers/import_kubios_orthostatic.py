#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
KubiosHRV Orthostatic-Import

@tier        infrastructure
@purpose.de  Importiert KubiosHRV Orthostatic-Exportdateien
@purpose.en  Imports KubiosHRV orthostatic export files
@method.de   Liest KubiosHRV-Exportdateien und importiert in v2: sessions (type='orthostatic') + session_metrics.
             Unterstuetzte Formate:
               1. KubiosHRV Standard TXT-Bericht (Desktop-Software, Windows/Mac)
               2. Manuelles CSV (Vorlage: --template)
             Datenquellen:
               kubios_polar_h10 - Kubios + Polar H10 Brustgurt (genaueste HRV-Werte)
               kubios_ble_hrm - Kubios + beliebiger BLE/ANT+-Brustgurt
               kubios_camera - Kubios Mobile App with Kamera-PPG (niedrigere Genauigkeit)
             Hinweis: hr_delta = hr_stand - hr_supine kann POTS unterschaetzen.
@method.en   Reads KubiosHRV export files and imports into v2: sessions (type='orthostatic') + session_metrics.
             Supported formats:
               1. KubiosHRV Standard TXT report (Desktop software, Windows/Mac)
               2. Manual CSV (template: --template)
             Data sources:
               kubios_polar_h10 - Kubios + Polar H10 chest strap (most accurate HRV)
               kubios_ble_hrm - Kubios + any BLE/ANT+ chest strap
               kubios_camera - Kubios Mobile App with camera PPG (lower accuracy)
             Note: hr_delta = hr_stand - hr_supine may underestimate POTS.
@reads       KubiosHRV TXT/CSV-Dateien
@writes      sessions, session_metrics
@limits.de   Segmentanalyse kann Peak-HR unterschaetzen.

@relevance.de  Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse
@relevance.en  Enables import of health data, essential for comprehensive data analysis
@limits.en   Segment analysis may underestimate peak HR.
@usage
    python import_kubios_orthostatic.py               # scannt imports/kubios/ (Default)
    python import_kubios_orthostatic.py --file export.txt
    python import_kubios_orthostatic.py --dir ~/Downloads/kubios/
    python import_kubios_orthostatic.py --csv messung.csv
    python import_kubios_orthostatic.py --template
    python import_kubios_orthostatic.py --manual
"""

import argparse
import re
from datetime import datetime
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import Config as _Cfg
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.base import log_import, resolve_person

_cfg = _Cfg()
DB_PATH = _cfg.db_path

CSV_TEMPLATE = """\
# Orthostatic-Messung (KubiosHRV or manuelle Input)
# columns: datum_uhrzeit,hr_supine,hr_standup_peak,hr_stand,rmssd_supine,rmssd_stand,quelle
#
# datum_uhrzeit   : YYYY-MM-DDTHH:MM:SS  (Messbeginn)
# hr_supine       : withtlere HR liegend (bpm)
# hr_standup_peak : Peak-HR beim Aufstehen (bpm); leer = gleich hr_stand
# hr_stand        : withtlere HR stehend (bpm)
# rmssd_supine    : RMSSD liegend (ms)
# rmssd_stand     : RMSSD stehend (ms)
# quelle          : kubios_polar_h10 | kubios_ble_hrm | kubios_camera | manuell
#
# Beispiel (Polar H10 via Kubios):
YYYY-MM-DDTHH:MM:SS,85.2,,108.7,22.1,4.8,kubios_polar_h10
"""

# ─── Kubios TXT Parser ────────────────────────────────────────────────────────

def _find_value(text: str, *patterns) -> float | None:
    """Sucht ersten Match einer beliebigen Regex-Liste and gibt float zurück."""
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            try:
                return float(m.group(1).replace(",", "."))
            except (ValueError, IndexError):
                pass
    return None


def _find_date(text: str) -> str | None:
    """Extrahiert Datum/Uhrzeit aus KubiosHRV-Bericht."""
    # Format: 28.01.2024  10:30:05
    m = re.search(r'Date[:\s]+(\d{1,2})\.(\d{2})\.(\d{4})\s+(\d{2}:\d{2}(?::\d{2})?)', text)
    if m:
        d, mo, y, t = m.groups()
        return f"{y}-{mo}-{d.zfill(2)}T{t if len(t) == 8 else t + ':00'}"
    # Format: YYYY-MM-DD  HH:MM:SS
    m = re.search(r'Date[:\s]+(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}(?::\d{2})?)', text)
    if m:
        d, t = m.groups()
        return f"{d}T{t if len(t) == 8 else t + ':00'}"
    # Only Datum, no Uhrzeit
    m = re.search(r'Date[:\s]+(\d{1,2})\.(\d{2})\.(\d{4})', text)
    if m:
        d, mo, y = m.groups()
        return f"{y}-{mo}-{d.zfill(2)}T00:00:00"
    return None


def _parse_kubios_txt(path: Path) -> dict | None:
    """
    Parst einen KubiosHRV Standard TXT-Bericht.
    Erwartet mindestens 2 Segmente: Liegend (Segment 1) and Stehend (Segment 2).
    """
    text = path.read_text(encoding="utf-8", errors="replace")

    # Datum
    dt = _find_date(text)
    if not dt:
        # Fallback: Filename enthält Datum (YYYYMMDD or YYYY-MM-DD)
        m = re.search(r'(\d{4}-?\d{2}-?\d{2})', path.stem)
        if m:
            d = m.group(1).replace("-", "")
            dt = f"{d[:4]}-{d[4:6]}-{d[6:8]}T00:00:00"

    if not dt:
        print(t(f"  ⚠ Kein Datum in {path.name} — übersprungen",
                f"  ⚠ No date in {path.name} — skipped"))
        return None

    # Device / Source
    device = "unbekannt"
    m = re.search(r'Device[:\s]+([^\n]+)', text, re.IGNORECASE)
    if m:
        device_str = m.group(1).strip().lower()
        if "h10" in device_str or "polar" in device_str:
            device = "kubios_polar_h10"
        elif "camera" in device_str or "kamera" in device_str:
            device = "kubios_camera"
        else:
            device = "kubios_ble_hrm"

    # Segmente extrahieren
    # Muster: alls zwischen "Segment N" and dem nächsten "Segment" or EOF
    segs = re.split(r'(?:Segment\s*\d+|Analysis\s+Segment)', text, flags=re.IGNORECASE)
    # segs[0] = Header, segs[1] = Segment 1 (Liegend), segs[2] = Segment 2 (Stehend)
    if len(segs) < 3:
        # Fallback: Split auf ---/=== Trennlinien and suche HR/RMSSD
        segs_alt = re.split(r'-{10,}|={10,}', text)
        segs = [s for s in segs_alt if re.search(r'Mean HR|RMSSD', s, re.IGNORECASE)]
        if len(segs) < 2:
            print(t(f"  ⚠ Weniger als 2 Segmente in {path.name} — übersprungen",
                    f"  ⚠ Fewer than 2 segments in {path.name} — skipped"))
            return None

    seg1 = segs[1]  # Supine
    seg2 = segs[2]  # Stand

    hr_pat  = [r'Mean HR[:\s]+([0-9]+\.?[0-9]*)\s*bpm']
    rms_pat = [r'RMSSD[:\s]+([0-9]+\.?[0-9]*)\s*ms']

    hr_sup  = _find_value(seg1, *hr_pat)
    hr_sta  = _find_value(seg2, *hr_pat)
    rms_sup = _find_value(seg1, *rms_pat)
    rms_sta = _find_value(seg2, *rms_pat)

    if hr_sup is None or hr_sta is None:
        print(t(f"  ⚠ Keine HR-Werte in {path.name} — übersprungen",
                f"  ⚠ No HR values in {path.name} — skipped"))
        return None

    hr_delta   = round(hr_sta - hr_sup, 1)
    rms_delta  = round((rms_sta or 0) - (rms_sup or 0), 1) if rms_sup and rms_sta else None

    return {
        "datetime":     dt,
        "hr_supine":    round(hr_sup, 1),
        "hr_standup":   round(hr_sta, 1),   # kein Peak verfügbar → gleich hr_stand
        "hr_stand":     round(hr_sta, 1),
        "rmssd_supine": round(rms_sup, 1) if rms_sup else None,
        "rmssd_stand":  round(rms_sta, 1) if rms_sta else None,
        "hr_delta":     hr_delta,
        "rmssd_delta":  rms_delta,
        "source":       device,
    }


def _parse_csv(path: Path) -> list[dict]:
    """Parst das manuelle CSV-Format (or jede Zeile without #)."""
    results = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 6:
            print(t(f"  ⚠ Ungültige Zeile (zu wenig Spalten): {line}",
                    f"  ⚠ Invalid row (too few columns): {line}"))
            continue
        try:
            dt        = parts[0]
            hr_sup    = float(parts[1]) if parts[1] else None
            hr_peak   = float(parts[2]) if parts[2] else None
            hr_sta    = float(parts[3]) if parts[3] else None
            rms_sup   = float(parts[4]) if parts[4] else None
            rms_sta   = float(parts[5]) if parts[5] else None
            source    = parts[6] if len(parts) > 6 else "kubios_unbekannt"

            if not hr_sup or not hr_sta:
                print(t(f"  ⚠ Fehlende HR-Werte: {line}",
                        f"  ⚠ Missing HR values: {line}"))
                continue

            hr_stand_val  = hr_peak if hr_peak else hr_sta
            hr_delta      = round(hr_stand_val - hr_sup, 1)
            rms_delta     = round((rms_sta or 0) - (rms_sup or 0), 1) if rms_sup and rms_sta else None

            results.append({
                "datetime":     dt,
                "hr_supine":    round(hr_sup, 1),
                "hr_standup":   round(hr_stand_val, 1),
                "hr_stand":     round(hr_sta, 1),
                "rmssd_supine": round(rms_sup, 1) if rms_sup else None,
                "rmssd_stand":  round(rms_sta, 1) if rms_sta else None,
                "hr_delta":     hr_delta,
                "rmssd_delta":  rms_delta,
                "source":       source,
            })
        except (ValueError, IndexError) as e:
            print(t(f"  ⚠ Fehler in Zeile '{line}': {e}",
                    f"  ⚠ Error in row '{line}': {e}"))
    return results


def _interactive() -> dict | None:
    """Interaktive manuelle Input eines Orthostatic-Tests."""
    print(t("\n=== Manuelle Orthostase-Eingabe ===", "\n=== Manual Orthostatic Entry ==="))
    print(t("Format: YYYY-MM-DDTHH:MM:SS (Enter für jetzt)",
            "Format: YYYY-MM-DDTHH:MM:SS (Enter for now)"))
    dt_in = input(t("Datum/Uhrzeit: ", "Date/Time: ")).strip()
    if not dt_in:
        dt_in = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    print(t("\nQuelle: 1=kubios_polar_h10  2=kubios_ble_hrm  3=kubios_camera  4=manuell",
            "\nSource: 1=kubios_polar_h10  2=kubios_ble_hrm  3=kubios_camera  4=manual"))
    src_map = {"1": "kubios_polar_h10", "2": "kubios_ble_hrm",
               "3": "kubios_camera",    "4": "manuell"}
    src_in = input(t("Quelle [1-4]: ", "Source [1-4]: ")).strip()
    source = src_map.get(src_in, "kubios_unbekannt")

    def _ask_float(prompt, required=True) -> float | None:
        while True:
            v = input(prompt).strip()
            if not v and not required:
                return None
            try:
                return float(v.replace(",", "."))
            except ValueError:
                print(t("  Bitte eine Zahl eingeben.", "  Please enter a number."))

    hr_sup  = _ask_float(t("HR liegend   (bpm): ", "HR supine   (bpm): "))
    hr_peak = _ask_float(t("HR Peak Aufstehen (bpm, leer = kein Peak): ",
                           "HR peak on standing (bpm, empty = no peak): "), required=False)
    hr_sta  = _ask_float(t("HR stehend   (bpm): ", "HR standing (bpm): "))
    rms_sup = _ask_float(t("RMSSD liegend (ms, leer): ", "RMSSD supine (ms, empty): "), required=False)
    rms_sta = _ask_float(t("RMSSD stehend (ms, leer): ", "RMSSD standing (ms, empty): "), required=False)

    hr_stand_val = hr_peak if hr_peak else hr_sta
    hr_delta     = round(hr_stand_val - hr_sup, 1)
    rms_delta    = round((rms_sta or 0) - (rms_sup or 0), 1) if rms_sup and rms_sta else None

    return {
        "datetime":     dt_in,
        "hr_supine":    round(hr_sup, 1),
        "hr_standup":   round(hr_stand_val, 1),
        "hr_stand":     round(hr_sta, 1),
        "rmssd_supine": round(rms_sup, 1) if rms_sup else None,
        "rmssd_stand":  round(rms_sta, 1) if rms_sta else None,
        "hr_delta":     hr_delta,
        "rmssd_delta":  rms_delta,
        "source":       source,
    }


def _to_utc(dt_local: str) -> str:
    """Approximate CET/CEST → UTC: subtract 2h Apr-Sep, 1h otherwise."""
    from datetime import timedelta
    try:
        month = int(dt_local[5:7])
        offset_h = 2 if 4 <= month <= 9 else 1
        dt = datetime.fromisoformat(dt_local[:19])
        return (dt - timedelta(hours=offset_h)).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    except Exception:
        return dt_local[:19] + "+00:00"


def _save_session(conn, r: dict, person: str) -> None:
    dt    = r["datetime"]
    clean = dt.replace(":", "").replace("-", "").replace("T", "T")[:15]
    sid   = f"kubios_ortho_{clean}"
    date  = dt[:10]
    ts    = _to_utc(dt)
    source_app = "kubios_desktop"

    conn.execute(
        "INSERT OR IGNORE INTO sessions"
        "(id, type, ts_start, date, device_id, person, source_app) "
        "VALUES (?, 'orthostatic', ?, ?, NULL, ?, ?)",
        (sid, ts, date, person, source_app)
    )

    metrics = [
        ("hr_supine",      r.get("hr_supine"),      None, "bpm"),
        ("hr_standup_min", r.get("hr_standup"),      None, "bpm"),
        ("hr_stand",       r.get("hr_stand"),        None, "bpm"),
        ("hr_delta",       r.get("hr_delta"),        None, "bpm"),
        ("rmssd_supine",   r.get("rmssd_supine"),    None, "ms"),
        ("rmssd_stand",    r.get("rmssd_stand"),     None, "ms"),
        ("rmssd_delta",    r.get("rmssd_delta"),     None, "ms"),
    ]
    for metric, value, value_text, unit in metrics:
        if value is None:
            continue
        conn.execute(
            "INSERT OR IGNORE INTO session_metrics(session_id, metric, value, value_text, unit) "
            "VALUES (?,?,?,?,?)",
            (sid, metric, value, value_text, unit)
        )


def _save(conn, records: list[dict], dry_run: bool = False, person: str | None = None) -> int:
    person = resolve_person(person)
    neu = 0
    for r in records:
        dt    = r["datetime"]
        clean = dt.replace(":", "").replace("-", "").replace("T", "T")[:15]
        sid   = f"kubios_ortho_{clean}"

        existing = conn.execute(
            "SELECT id FROM sessions WHERE id = ?", (sid,)
        ).fetchone()
        if existing:
            print(t(f"  ↺ Bereits vorhanden: {dt[:16]} — übersprungen",
                    f"  ↺ Already exists: {dt[:16]} — skipped"))
            continue

        if dry_run:
            print(t(f"  [DRY] {dt[:16]}  HR: {r['hr_supine']}→{r['hr_stand']} bpm  "
                    f"ΔHR={r['hr_delta']:+.0f}  RMSSD: {r.get('rmssd_supine')}→{r.get('rmssd_stand')}  "
                    f"Quelle: {r['source']}",
                    f"  [DRY] {dt[:16]}  HR: {r['hr_supine']}→{r['hr_stand']} bpm  "
                    f"ΔHR={r['hr_delta']:+.0f}  RMSSD: {r.get('rmssd_supine')}→{r.get('rmssd_stand')}  "
                    f"Source: {r['source']}"))
            neu += 1
            continue

        _save_session(conn, r, person)
        print(t(f"  ✓ {dt[:16]}  ΔHR={r['hr_delta']:+.0f} bpm  Quelle: {r['source']}",
                f"  ✓ {dt[:16]}  ΔHR={r['hr_delta']:+.0f} bpm  Source: {r['source']}"))
        neu += 1

    if not dry_run and neu > 0:
        log_import(conn, 'kubios_orthostatic', '', neu, person=person)
        conn.commit()
    return neu


def main():
    parser = argparse.ArgumentParser(
        description="KubiosHRV Orthostase-Daten importieren")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--file",     metavar="DATEI",  help="KubiosHRV TXT-Bericht")
    group.add_argument("--dir",      metavar="ORDNER", help="Ordner mit TXT-Berichten")
    group.add_argument("--csv",      metavar="DATEI",  help="Manuelles CSV")
    group.add_argument("--manual",   action="store_true", help="Interaktive Eingabe")
    group.add_argument("--template", action="store_true", help="CSV-Vorlage ausgeben")
    parser.add_argument("--dry-run", action="store_true",
                        help="Vorschau ohne Datenbankschreibzugriff")
    parser.add_argument("--person", default=None, help="Ziel-Person (Default: OWN_PERSON_ID)")
    add_lang_arg(parser)

    args = parser.parse_args()
    apply_lang_from_args(args)

    if args.template:
        print(CSV_TEMPLATE)
        return

    records: list[dict] = []

    if args.file:
        p = Path(args.file)
        r = _parse_kubios_txt(p)
        if r:
            records.append(r)

    elif args.dir or (not args.file and not args.csv and not args.manual):
        d = Path(args.dir) if args.dir else _cfg.kubios_dir
        txts = list(d.glob("*.txt")) + list(d.glob("*.TXT"))
        print(t(f"Ordner: {d}  |  Gefundene TXT-Dateien: {len(txts)}",
                f"Folder: {d}  |  TXT files found: {len(txts)}"))
        for p in sorted(txts):
            r = _parse_kubios_txt(p)
            if r:
                records.append(r)

    elif args.csv:
        records = _parse_csv(Path(args.csv))

    elif args.manual:
        r = _interactive()
        if r:
            records.append(r)

    if not records:
        print(t("Keine verwertbaren Datensätze gefunden.", "No usable records found."))
        return

    print(t(f"\n{len(records)} Datensatz/-sätze zum Import:",
            f"\n{len(records)} record(s) to import:"))
    conn = open_db()
    n = _save(conn, records, dry_run=args.dry_run, person=args.person)
    conn.close()

    if args.dry_run:
        print(t(f"\nDRY-RUN: {n} Datensätze würden importiert. Ohne --dry-run erneut ausführen.",
                f"\nDRY-RUN: {n} record(s) would be imported. Re-run without --dry-run."))
    else:
        print(t(f"\n{n} Datensatz/-sätze neu importiert.", f"\n{n} record(s) newly imported."))
        if n > 0:
            print(t("Auswertung: python analyse/analyse_orthostatic.py --plot",
                    "Analysis: python analyse/analyse_orthostatic.py --plot"))


if __name__ == "__main__":
    main()
