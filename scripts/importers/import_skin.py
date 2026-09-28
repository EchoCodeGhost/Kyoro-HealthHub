#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
import_skin.py — Hautlaesionen importieren (source-agnostisch)

@tier        infrastructure
@purpose.de  Importiert Hautlaesions-Fotos und Metadaten aus verschiedenen Quellen in die medicine.db
@purpose.en  Imports skin lesion photos and metadata from various sources into medicine.db
@method.de   Akzeptiert Bilder aus Smartphone-Kamera, Screenshots (Skinscreener/SkinVision), DSLR oder anderen JPEG/PNG Quellen.
             Jede Laesion erhaelt eine persistente ID in skin_lesions. Folgefotos werden ueber --lesion-id verknuepft.
             Fotos werden in imaging_files gespeichert mit Referenz auf die Laesion.
             Klinische Outcomes (Hautarzt-Befund, Operation, Histologie) koennen ueber --update-lesion nachgetragen werden.
             Bilder werden automatisch nach JPEG normalisiert und mit anonymisierten Dateinamen gespeichert.
@method.en   Accepts images from smartphone camera, screenshots (Skinscreener/SkinVision), DSLR, or other JPEG/PNG sources.
             Each lesion receives a persistent ID in skin_lesions. Follow-up photos are linked via --lesion-id.
             Photos are stored in imaging_files with reference to the lesion.
             Clinical outcomes (dermatologist assessment, operation, histology) can be added via --update-lesion.
             Images are automatically normalized to JPEG and stored with anonymized filenames.
@reads       Bilddateien (JPEG/PNG/HEIC/MOV) aus Inbox-Verzeichnissen oder als Argument
@writes      skin_lesions, imaging_files, user_context, import_log
@limits.de   Abhaengig von Bildqualitaet und Metadaten-Verfuegbarkeit. Keine automatische Bildanalyse.
             Histologie-Befunde muessen manuell erfasst werden.

@relevance.de  Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse
@relevance.en  Enables import of health data, essential for comprehensive data analysis
@limits.en   Depends on image quality and metadata availability. No automatic image analysis.
             Histology results must be entered manually.
@usage
    python3 scripts/importers/import_skin.py foto.jpg --location "Ruecken links, 5cm unterhalb Schulterblatt" --date 2026-06-28 --source camera
    python3 scripts/importers/import_skin.py foto2.jpg --lesion-id 3
    python3 scripts/importers/import_skin.py --update-lesion 3 --app-score mittel --app-name Skinscreener
    python3 scripts/importers/import_skin.py --update-lesion 3 --derm-assessment "Compound-Naevus, unauffaellig" --derm-date 2026-08-15
    # VLM-Analyse ist ein separater Schritt: scripts/analysis/manual/analyse_skin.py --analyse
    python3 scripts/importers/import_skin.py --list-lesions
"""

import argparse
import shutil
import sys
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from health_config import Config, OWN_PERSON_ID
from modules.base import log_import
from modules.db import open_medicine_imaging_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.imaging_utils import (
    normalize_to_jpeg, is_supported, RAW_EXTENSIONS, process_raw, record_photo_location,
)

_cfg = Config()

SKIN_DIR     = _cfg.data_root.parent / "data" / "skin"
ANALYSES_DIR = _cfg.analyses_dir / "skin"

SOURCE_TYPES = ("camera", "screenshot", "dslr", "other")
APP_SCORES   = ("niedrig", "mittel", "hoch")

# Inbox-Pfade, die bei fehlendem photos-Argument automatisch gescannt werden (Priorität: oben)
_INBOX_ROOTS = [
    _cfg.data_root / "_inbox" / "skin_images",
    _cfg.data_root / "skin_images",
    _cfg.data_root / "_inbox",
]


def _discover_inbox() -> list[Path]:
    """Scannt bekannte Inbox-Pfade und gibt alle unterstützten Bilddateien zurück."""
    found: list[Path] = []
    for root in _INBOX_ROOTS:
        if root.is_dir():
            for f in sorted(root.iterdir()):
                if f.is_file() and is_supported(f):
                    found.append(f)
            if found:
                print(t(f"Inbox: {len(found)} Datei(en) in {root}",
                        f"Inbox: {len(found)} file(s) in {root}"))
                return found
    return []


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ensure_dirs() -> None:
    SKIN_DIR.mkdir(parents=True, exist_ok=True)
    ANALYSES_DIR.mkdir(parents=True, exist_ok=True)


def _safe_copy(src: Path, photo_date: str, lesion_id: int, idx: int = 1) -> Path:
    """Kopiert Foto mit anonymisiertem Dateinamen."""
    ext  = src.suffix.lower() or ".jpg"
    name = f"skin_{photo_date.replace('-','')}_{lesion_id:04d}_{idx:02d}{ext}"
    dst  = SKIN_DIR / name
    i    = idx
    while dst.exists():
        i  += 1
        name = f"skin_{photo_date.replace('-','')}_{lesion_id:04d}_{i:02d}{ext}"
        dst  = SKIN_DIR / name
    shutil.copy2(src, dst)
    return dst


# ── Läsionen auflisten ────────────────────────────────────────────────────────

def list_lesions(conn) -> None:
    rows = conn.execute("""
        SELECT l.id, l.body_location, l.first_seen, l.last_checked,
               l.app_score, l.dermatologist_assessment, l.operated, l.histology,
               COUNT(f.id) AS fotos
        FROM skin_lesions l
        LEFT JOIN imaging_files f ON f.lesion_id = l.id
        WHERE l.person=?
        GROUP BY l.id ORDER BY l.first_seen DESC
    """, (OWN_PERSON_ID,)).fetchall()

    if not rows:
        print(t("Keine Läsionen in der DB.", "No lesions in DB."))
        return

    print(t(f"\n{'ID':>4}  {'Erstgesehen':>12}  {'Zuletzt':>12}  "
            f"{'Fotos':>5}  {'App':>7}  {'OP':>3}  {'Histologie':<20}  Ort",
            f"\n{'ID':>4}  {'First seen':>12}  {'Last':>12}  "
            f"{'Photos':>6}  {'App':>7}  {'OP':>3}  {'Histology':<20}  Location"))
    print("─" * 100)
    for lid, loc, first, last, app, derm, op, hist, fotos in rows:
        op_str   = "✓" if op else "-"
        hist_str = (hist or "-")[:20]
        app_str  = app or "-"
        last_str = last or "-"
        print(f"{lid:>4}  {first:>12}  {last_str:>12}  {fotos:>5}  "
              f"{app_str:>7}  {op_str:>3}  {hist_str:<20}  {loc}")


# ── Läsion anlegen / abrufen ──────────────────────────────────────────────────

def _get_or_create_lesion(conn, location: str, first_seen: str,
                           app_score: str | None, app_name: str | None) -> int:
    row = conn.execute(
        "SELECT id FROM skin_lesions WHERE person=? AND body_location=? AND first_seen=?",
        (OWN_PERSON_ID, location, first_seen)
    ).fetchone()
    if row:
        return row[0]
    conn.execute("""
        INSERT INTO skin_lesions (person, body_location, first_seen, app_score, app_name)
        VALUES (?,?,?,?,?)
    """, (OWN_PERSON_ID, location, first_seen, app_score, app_name))
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


# ── Läsion aktualisieren ──────────────────────────────────────────────────────

def update_lesion(conn, lesion_id: int, args) -> None:
    updates: list[str] = []
    values:  list      = []

    if args.app_score:
        updates.append("app_score=?");        values.append(args.app_score)
    if args.app_name:
        updates.append("app_name=?");         values.append(args.app_name)
    if args.derm_assessment:
        updates.append("dermatologist_assessment=?"); values.append(args.derm_assessment)
    if args.derm_date:
        updates.append("dermatologist_date=?"); values.append(args.derm_date)
    if args.operated:
        updates.append("operated=1")
    if args.operation_date:
        updates.append("operation_date=?");   values.append(args.operation_date)
    if args.histology:
        updates.append("histology=?");        values.append(args.histology)
    if args.histology_subtype:
        updates.append("histology_subtype=?"); values.append(args.histology_subtype)
    if args.histology_date:
        updates.append("histology_date=?");   values.append(args.histology_date)
    if args.notes:
        updates.append("notes=?");            values.append(args.notes)

    if not updates:
        print(t("Keine Felder zum Aktualisieren angegeben.", "No fields to update specified."))
        return

    values.append(lesion_id)
    conn.execute(f"UPDATE skin_lesions SET {', '.join(updates)} WHERE id=?", values)
    conn.commit()
    print(t(f"Läsion {lesion_id} aktualisiert.", f"Lesion {lesion_id} updated."))
    print(t(
        f"  ℹ Erinnerung: analyse_skin.py läuft nicht automatisch mit — "
        f"für einen aktuellen Bericht: python3 scripts/analysis/manual/analyse_skin.py --lesion {lesion_id}",
        f"  ℹ Reminder: analyse_skin.py does not run automatically — "
        f"for an up-to-date report: python3 scripts/analysis/manual/analyse_skin.py --lesion {lesion_id}"))


# ── Foto importieren ──────────────────────────────────────────────────────────

def import_photo(conn, src: Path, lesion_id: int, photo_date: str,
                 source_type: str) -> int:
    import tempfile
    gps = None
    raw_dst = None
    with tempfile.TemporaryDirectory() as _tmp:
        tmp_dir = Path(_tmp)
        if src.suffix.lower() in RAW_EXTENSIONS:
            # Weg 2: RAW-Original (metadatenbereinigt) UND JPEG-Vorschau behalten
            result = process_raw(src, tmp_dir)
            exif_dt, gps = result["date"], result["gps"]
            if exif_dt and photo_date == date.today().isoformat():
                photo_date = exif_dt
            dst     = _safe_copy(result["jpeg_path"], photo_date, lesion_id)
            raw_dst = _safe_copy(result["raw_path"], photo_date, lesion_id,
                                  idx=int(dst.stem.rsplit("_", 1)[-1]))
        else:
            normalized, exif_dt, gps = normalize_to_jpeg(src, tmp_dir)
            if exif_dt and photo_date == date.today().isoformat():
                photo_date = exif_dt
            dst = _safe_copy(normalized, photo_date, lesion_id)
    now = datetime.now(timezone.utc).isoformat()

    if gps:
        from modules.db import open_db
        health_conn = open_db()
        try:
            record_photo_location(health_conn, photo_date, gps, "import_skin", OWN_PERSON_ID)
            health_conn.commit()
        finally:
            health_conn.close()

    conn.execute("""
        INSERT OR IGNORE INTO imaging_files
          (person, file_path, original_format, acquisition_date,
           modality, body_part, source_type, lesion_id, raw_file_path, image_type, ts_import)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
    """, (OWN_PERSON_ID, str(dst), src.suffix.lower().lstrip("."),
          photo_date, "PHOTO", "SKIN", source_type, lesion_id,
          str(raw_dst) if raw_dst else None, "skin_lesion", now))
    file_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    conn.execute(
        "UPDATE skin_lesions SET last_checked=? WHERE id=? AND (last_checked IS NULL OR last_checked<?)",
        (photo_date, lesion_id, photo_date)
    )

    print(t(f"  ✓ {src.name} → {dst.name}  [Läsion {lesion_id}]",
            f"  ✓ {src.name} → {dst.name}  [Lesion {lesion_id}]"))
    return file_id


# ── Hauptfunktion ─────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(
        description=t("Hautläsionen importieren (source-agnostisch)",
                      "Import skin lesion photos (source-agnostic)")
    )

    # Foto-Import
    ap.add_argument("photos", nargs="*",
                    help=t("JPEG/PNG/HEIC/MOV-Dateien", "JPEG/PNG/HEIC/MOV files"))
    ap.add_argument("--lesion-id", type=int, default=None,
                    help=t("Vorhandene Läsions-ID (Folgefoto)", "Existing lesion ID (follow-up)"))
    ap.add_argument("--location",
                    help=t("Körperstelle — Freitext (Pflicht für neue Läsion)",
                           "Body location — free text (required for new lesion)"))
    ap.add_argument("--date", dest="photo_date", default=None,
                    help=t("Fotodatum YYYY-MM-DD (Standard: heute)", "Photo date YYYY-MM-DD (default: today)"))
    ap.add_argument("--source", choices=SOURCE_TYPES, default="camera",
                    help=t("Fotoherkunft: camera|screenshot|dslr|other",
                           "Photo source: camera|screenshot|dslr|other"))

    # App-Score
    ap.add_argument("--app-score", choices=APP_SCORES,
                    help=t("App-Risikobewertung: niedrig|mittel|hoch",
                           "App risk score: low|medium|high"))
    ap.add_argument("--app-name",
                    help=t("App-Name (z.B. Skinscreener)", "App name (e.g. Skinscreener)"))

    # Klinische Outcomes (per --update-lesion)
    ap.add_argument("--update-lesion", type=int, dest="update_lesion", metavar="ID",
                    help=t("Läsion aktualisieren (kein Foto nötig)",
                           "Update lesion metadata (no photo needed)"))
    ap.add_argument("--derm-assessment",
                    help=t("Hautarzt-Befund (Freitext)", "Dermatologist assessment (free text)"))
    ap.add_argument("--derm-date",
                    help=t("Datum Hautarzt-Termin YYYY-MM-DD", "Dermatologist visit date YYYY-MM-DD"))
    ap.add_argument("--operated", action="store_true",
                    help=t("Läsion wurde operiert/entfernt", "Lesion was operated/removed"))
    ap.add_argument("--operation-date",
                    help=t("Datum der Operation YYYY-MM-DD", "Operation date YYYY-MM-DD"))
    ap.add_argument("--histology",
                    help=t("Histologie-Ergebnis (z.B. 'Basalzellkarzinom')",
                           "Histology result (e.g. 'Basal cell carcinoma')"))
    ap.add_argument("--histology-subtype",
                    help=t("Histologie-Subtyp (z.B. 'nodulär', 'Clark Level II')",
                           "Histology subtype"))
    ap.add_argument("--histology-date",
                    help=t("Datum des Histologie-Befunds YYYY-MM-DD", "Histology report date"))
    ap.add_argument("--notes", help=t("Freie Notiz zur Läsion", "Free note for lesion"))

    # Utility
    ap.add_argument("--list-lesions", action="store_true",
                    help=t("Alle bekannten Läsionen auflisten", "List all known lesions"))

    add_lang_arg(ap)
    args = ap.parse_args()
    apply_lang_from_args(args)

    _ensure_dirs()
    conn = open_medicine_imaging_db()

    if args.list_lesions:
        list_lesions(conn)
        conn.close()
        return

    if args.update_lesion:
        update_lesion(conn, args.update_lesion, args)
        conn.close()
        return

    if not args.photos:
        args.photos = [str(p) for p in _discover_inbox()]
    if not args.photos:
        print(t(
            "Keine Dateien angegeben und Inbox leer.\n"
            f"Inbox-Pfade: {', '.join(str(r) for r in _INBOX_ROOTS)}",
            "No files given and inbox empty.\n"
            f"Inbox paths: {', '.join(str(r) for r in _INBOX_ROOTS)}",
        ))
        conn.close()
        return

    photo_date = args.photo_date or date.today().isoformat()
    total      = 0

    for photo_str in args.photos:
        src = Path(photo_str)
        if not src.exists():
            print(t(f"Datei nicht gefunden: {src}", f"File not found: {src}"), file=sys.stderr)
            continue

        if args.lesion_id:
            lesion_id = args.lesion_id
            row = conn.execute("SELECT body_location FROM skin_lesions WHERE id=?",
                               (lesion_id,)).fetchone()
            if not row:
                print(t(f"Läsion {lesion_id} nicht gefunden.", f"Lesion {lesion_id} not found."),
                      file=sys.stderr)
                continue
            print(t(f"Folgefoto für Läsion {lesion_id}: {row[0]}",
                    f"Follow-up photo for lesion {lesion_id}: {row[0]}"))
        else:
            if not args.location:
                print(t("--location ist Pflicht für neue Läsionen.",
                        "--location is required for new lesions."), file=sys.stderr)
                conn.close()
                sys.exit(1)
            lesion_id = _get_or_create_lesion(
                conn, args.location, photo_date, args.app_score, args.app_name
            )
            print(t(f"Neue Läsion angelegt: ID {lesion_id}  [{args.location}]",
                    f"New lesion created: ID {lesion_id}  [{args.location}]"))

        import_photo(conn, src, lesion_id, photo_date, args.source)
        total += 1

    log_import(conn, "import_skin", "", total)
    conn.commit()
    conn.close()
    print(t(f"\n{total} Foto(s) importiert.", f"\n{total} photo(s) imported."))


if __name__ == "__main__":
    main()
