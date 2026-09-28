#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Apple Watch ECG CSV → health.db (ecg_sessions + ecg_samples)

@tier        infrastructure
@purpose.de  Importiert Apple Watch ECG-Daten
@purpose.en  Imports Apple Watch ECG data
@method.de   Importiert ECG-CSV-Dateien aus dem Apple Health Export
             (Unterordner electrocardiograms/) in zwei Tabellen:
             - ecg_sessions: Metadaten (Datum, Klassifizierung, Lead, Dauer)
             - ecg_samples: Rohdaten (uV-Werte bei 512 Hz, Lead I)
             Dateiformat Apple Health Export: Schluessel/Wert-Metadaten,
             Trennzeile, Einheitszeile, Messpunkte als deutsches Dezimalkomma.
@method.en   Imports ECG CSV files from Apple Health Export
             (subfolder electrocardiograms/) into two tables:
             - ecg_sessions: metadata (date, classification, lead, duration)
             - ecg_samples: raw data (uV values at 512 Hz, lead I)
             File format: key/value metadata, separator line, unit line, measurement points as German decimal comma.
@reads       Apple Health Export CSV-Dateien
@writes      ecg_sessions, ecg_samples
@limits.de   Nur Apple Watch ECG-Dateien. Abhaengig von Exportformat.

@relevance.de  Ermöglicht den Import von Gesundheitsdaten aus Apple Health, essentiell für die Integration von iOS-Gesundheitsdaten
@relevance.en  Enables import of health data from Apple Health, essential for integration of iOS health data
@limits.en   Only Apple Watch ECG files. Dependent on export format.
@usage
    python3 import_ecg_apple.py --dir imports/apple_health/electrocardiograms/
    python3 import_ecg_apple.py --dry-run --no-samples
"""

import argparse
import csv
from datetime import datetime, timezone
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.base import log_import

_cfg = _Cfg()
DB_PATH = _cfg.db_path

# Apple Watch ECG-Klassifizierungen → kanonische DB-Werte
CLASSIF_MAP = {
    # Deutsch
    "Sinusrhythmus":                            "sinus_rhythm",
    "Vorhofflimmern":                           "atrial_fibrillation",
    "Nicht schlüssig":                          "inconclusive",
    "Uneindeutig":                              "inconclusive",
    "Hohe Herzfrequenz":                        "high_heart_rate",
    "Hohes Herzfrequenz":                       "high_heart_rate",
    "Niedrige Herzfrequenz":                    "low_heart_rate",
    "Schlechte Aufzeichnung":                   "poor_recording",
    "Sinusrhythmus mit PR-Verlängerung":        "sinus_pr_prolonged",
    "Sinusrhythmus mit ungewöhnlichem QRS":     "sinus_unusual_qrs",
    # Englisch (für ältere oder englischsprachige Exports)
    "Sinus Rhythm":                             "sinus_rhythm",
    "Atrial Fibrillation":                      "atrial_fibrillation",
    "Inconclusive":                             "inconclusive",
    "High Heart Rate":                          "high_heart_rate",
    "Low Heart Rate":                           "low_heart_rate",
    "Poor Recording":                           "poor_recording",
}


def _parse_sample_value(row: list) -> float | None:
    """
    Apple Health ECG CSVs verwenden deutsches Dezimalkomma (z.B. "35,816").
    Der csv.reader splittet das in zwei Felder ['35', '816'].
    Diese Funktion fügt sie wieder zu 35.816 zusammen.
    Funktioniert auch für negative Werte: '-2', '648' → -2.648
    """
    try:
        integer_part = row[0].strip()
        if len(row) >= 2 and row[1].strip():
            return float(f"{integer_part}.{row[1].strip()}")
        return float(integer_part)
    except (ValueError, IndexError):
        return None


def parse_ecg_csv(path: Path) -> tuple[dict, list[float]] | None:
    """Liest Metadaten und µV-Samples aus einer Apple-ECG-CSV."""
    meta: dict = {}
    samples: list[float] = []
    in_data = False

    with open(path, encoding="utf-8-sig", newline="") as fh:
        reader = csv.reader(fh)
        for row in reader:
            if not row:
                continue

            key = row[0].strip()

            if in_data:
                val = _parse_sample_value(row)
                if val is not None:
                    samples.append(val)
                continue

            val_raw = row[1].strip() if len(row) > 1 else ""

            if key in ("Name", "Geburtstag", "Birthday", "Date of Birth"):
                pass
            elif key in ("Aufzeichnungsdatum", "Recording Date"):
                # "2025-09-22 19:12:10 +0200" → UTC → "2025-09-22T17:12:10"
                try:
                    parsed = datetime.strptime(val_raw.strip(), "%Y-%m-%d %H:%M:%S %z")
                    meta["datetime"] = parsed.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
                except (ValueError, AttributeError):
                    meta["datetime"] = val_raw[:19].replace(" ", "T") if val_raw else None
            elif key in ("Klassifizierung", "Classification"):
                meta["classification"] = CLASSIF_MAP.get(val_raw, val_raw.lower().replace(" ", "_"))
            elif key in ("Symptome", "Symptoms"):
                meta["symptoms"] = val_raw or None
            elif key in ("Softwareversion", "Software Version"):
                meta["software_ver"] = val_raw or None
            elif key in ("Gerät", "Device"):
                meta["device"] = val_raw or None
            elif key in ("Messrate", "Sampling Rate"):
                # "512 Hertz" or "512\xa0Hertz"
                try:
                    meta["sample_rate_hz"] = int(val_raw.split()[0])
                except (ValueError, IndexError):
                    meta["sample_rate_hz"] = 512
            elif key in ("Ableitung", "Lead Name"):
                meta["lead"] = val_raw or "Ableitung I"
                in_data = True
            elif key in ("Einheit", "Unit"):
                pass  # µV — already known

    if not meta.get("datetime"):
        return None
    meta["n_samples"] = len(samples)
    return meta, samples


def _device_id_from_meta(meta: dict) -> str | None:
    """Mappt Apple-interne Gerätekennzeichnung auf einen menschenlesbaren Bezeichner."""
    device = meta.get("device", "")
    # Apple Watch Modell-Codes: Watch4,x = Series 4, Watch5,x = S5, ..., Watch7,x = S9
    mapping = {
        "Watch4": "apple_watch_s4",
        "Watch5": "apple_watch_s5",
        "Watch6": "apple_watch_s6_se",
        "Watch7": "apple_watch_s9",
        "Watch8": "apple_watch_ultra2",
    }
    prefix = device[:6] if device else ""
    return mapping.get(prefix, device or None)


def _save(conn, meta: dict, samples: list[float],
              person: str, dry_run: bool, force_samples: bool = False) -> bool:
    dt = meta["datetime"]
    n  = meta["n_samples"]
    hz = meta.get("sample_rate_hz", 512)

    session_exists = conn.execute(
        "SELECT 1 FROM ecg_sessions WHERE datetime = ? AND person = ?", (dt, person)
    ).fetchone() is not None

    samples_exist = session_exists and conn.execute(
        "SELECT 1 FROM ecg_samples WHERE session_dt = ? AND session_person = ? LIMIT 1",
        (dt, person)
    ).fetchone() is not None

    needs_samples = bool(samples) and (not samples_exist or force_samples)

    if session_exists and not needs_samples:
        return False  # vollständig vorhanden

    duration  = n / hz if hz and n else None
    device_id = _device_id_from_meta(meta)
    classif   = meta.get("classification", "unknown")
    lead      = meta.get("lead", "Ableitung I")

    if dry_run:
        action = t("SAMPLES-FIX", "SAMPLES-FIX") if (session_exists and needs_samples) else t("NEU", "NEW")
        afib_marker = "  *** AFib ***" if classif == "atrial_fibrillation" else ""
        print(t(f"  [DRY/{action}] {dt[:16]}  {classif:<28}  {n:>5} Samples{afib_marker}",
                f"  [DRY/{action}] {dt[:16]}  {classif:<28}  {n:>5} samples{afib_marker}"))
        return True

    if not session_exists:
        conn.execute("""
            INSERT INTO ecg_sessions
              (datetime, classification, symptoms, sample_rate_hz,
               lead, duration_s, device_id, person, source)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, (dt, classif, meta.get("symptoms"),
              hz, lead, duration, device_id, person, "apple_health"))

    if needs_samples:
        conn.execute(
            "DELETE FROM ecg_samples WHERE session_dt = ? AND session_person = ?",
            (dt, person)
        )
        conn.executemany(
            "INSERT INTO ecg_samples (session_dt, session_person, sample_index, uv) "
            "VALUES (?,?,?,?)",
            [(dt, person, i, v) for i, v in enumerate(samples)]
        )

    conn.commit()
    return True


def main():
    default_dir = str(
        _cfg.data_root.parent / "imports" / "apple_health_export" / "electrocardiograms"
    )

    parser = argparse.ArgumentParser(
        description=t("Apple Watch ECG CSV importieren", "Import Apple Watch ECG CSV"))
    parser.add_argument("--dir", default=default_dir,
                        help=t("Pfad zum electrocardiograms/-Ordner",
                               "Path to electrocardiograms/ folder"))
    parser.add_argument("--person", default=OWN_PERSON_ID,
                        help=t("Person (default: self)", "Person (default: self)"))
    parser.add_argument("--dry-run", action="store_true",
                        help=t("Nur anzeigen, nicht schreiben", "Show only, do not write"))
    parser.add_argument("--no-samples", action="store_true",
                        help=t("Nur Metadaten, keine µV-Rohdaten",
                               "Metadata only, skip raw µV samples"))
    parser.add_argument("--force-samples", action="store_true",
                        help=t("Samples neu schreiben auch wenn Session schon existiert "
                               "(behebt falsch importierte Dezimalwerte)",
                               "Re-import samples even if session exists "
                               "(fixes incorrectly parsed decimal values)"))
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)

    ecg_dir = Path(args.dir).expanduser()
    if not ecg_dir.exists():
        print(t(f"Verzeichnis nicht gefunden: {ecg_dir}",
                f"Directory not found: {ecg_dir}"))
        sys.exit(1)

    paths = sorted(ecg_dir.glob("*.csv"))
    if not paths:
        print(t("Keine CSV-Dateien gefunden.", "No CSV files found."))
        return

    conn = open_db()
    conn.execute("PRAGMA journal_mode=WAL")

    neu = skip = err = 0
    by_classification: dict[str, int] = {}

    for p in paths:
        result = parse_ecg_csv(p)
        if result is None:
            print(t(f"  Kein Datum in {p.name}", f"  No date found in {p.name}"))
            err += 1
            continue

        meta, samples = result
        if args.no_samples:
            samples = []

        classif = meta.get("classification", "unknown")

        ok = _save(conn, meta, samples, args.person, args.dry_run,
                       force_samples=args.force_samples)
        if ok:
            neu += 1
            by_classification[classif] = by_classification.get(classif, 0) + 1
            afib = "  *** AFib ***" if classif == "atrial_fibrillation" else ""
            print(f"  {meta['datetime'][:16]}  {classif:<28}  "
                  f"{meta['n_samples']:>5} Samples  {p.name}{afib}")
        else:
            skip += 1

    if not args.dry_run:
        log_import(conn, 'ecg_apple', str(ecg_dir), neu)
        conn.commit()
    conn.close()

    print(t(f"\n{neu} neu importiert | {skip} bereits vorhanden | {err} Fehler",
            f"\n{neu} newly imported | {skip} already present | {err} errors"))
    print(t("Klassifizierungen:", "Classifications:"))
    for cls, n in sorted(by_classification.items(), key=lambda x: -x[1]):
        print(f"  {cls:<30} {n:>3}")

    if by_classification.get("atrial_fibrillation", 0) > 0:
        n_afib = by_classification["atrial_fibrillation"]
        print(t(f"\n*** {n_afib} AFib-Aufnahmen NEU importiert ***",
                f"\n*** {n_afib} AFib recordings newly imported ***"))

    if neu > 0 and not args.dry_run:
        print(t(
            "  ℹ Erinnerung: analyse_ecg_session.py läuft nicht automatisch mit — "
            "für einen Einzelsession-Bericht: python3 scripts/analysis/manual/analyse_ecg_session.py --session <ID>",
            "  ℹ Reminder: analyse_ecg_session.py does not run automatically — "
            "for a single-session report: python3 scripts/analysis/manual/analyse_ecg_session.py --session <ID>"))


if __name__ == "__main__":
    main()
