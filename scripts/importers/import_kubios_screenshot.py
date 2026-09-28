#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Kubios HRV Screenshot-Import

@tier        infrastructure
@purpose.de  Importiert Kubios HRV Mobile Screenshots per OCR
@purpose.en  Imports Kubios HRV Mobile screenshots via OCR
@method.de   Liest Kubios HRV Mobile Screenshots (PNG) per OCR und importiert die Werte
             in kubios_hrv_resting.
             Unterstuetzt:
               - Kubios HRV Mobile "RESTING HRV" Resultscreen
               - macOS-Screenshots
               - Beliebige PNG-Screenshots (Datum aus File-Metadaten)
             Alle Werte werden extrahiert, inkl. PNS/SNS-Index.
@method.en   Reads Kubios HRV Mobile screenshots (PNG) via OCR and imports the values
             into kubios_hrv_resting.
             Supports:
               - Kubios HRV Mobile "RESTING HRV" result screen
               - macOS screenshots
               - Any PNG screenshots (date from file metadata)
             All values are extracted, including PNS/SNS index.
@reads       PNG-Screenshots
@writes      kubios_hrv_resting
@limits.de   OCR kann ungenau sein. Abhaengig von Screenshot-Qualitaet.

@relevance.de  Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse
@relevance.en  Enables import of health data, essential for comprehensive data analysis
@limits.en   OCR may be inaccurate. Dependent on screenshot quality.
@usage
    python import_kubios_screenshot.py               # scannt imports/kubios/ (Default)
    python import_kubios_screenshot.py --file screenshot.png
    python import_kubios_screenshot.py --dir ~/Downloads/kubios/
    python import_kubios_screenshot.py --file screenshot.png --dry-run
"""

import argparse
import re
from datetime import datetime
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.base import log_import

_cfg = _Cfg()
DB_PATH = _cfg.db_path



def _datum_aus_dateiname(path: Path) -> str | None:
    """macOS: 'Bildschirmfoto YYYY-MM-DD um HH.MM.SS.png' → 'YYYY-MM-DDT13:16:25'"""
    m = re.search(r'(\d{4}-\d{2}-\d{2})\s+um\s+(\d{2})\.(\d{2})\.(\d{2})', path.name)
    if m:
        d, hh, mm, ss = m.groups()
        return f"{d}T{hh}:{mm}:{ss}"
    # iOS/Android Timestamp-Namen: IMG_1746044871490.png → Unix-ms
    m = re.search(r'IMG_(\d{10})\d*\.png', path.name, re.IGNORECASE)
    if m:
        ts = int(m.group(1))
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%dT%H:%M:%S")
    # Fallback: File-Änderungszeit
    mtime = path.stat().st_mtime
    return datetime.fromtimestamp(mtime).strftime("%Y-%m-%dT%H:%M:%S")


def _parse_float(text: str, *patterns) -> float | None:
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            try:
                return float(m.group(1).replace(",", "."))
            except (ValueError, IndexError):
                pass
    return None


def _parse_int(text: str, *patterns) -> int | None:
    v = _parse_float(text, *patterns)
    return int(round(v)) if v is not None else None


def _ocr_chip_value(arr, h: int, y1f: float, y2f: float,
                    x_search_start: int, x_search_end: int) -> float | None:
    """
    Extrahiert den Zahlenwert aus einem Kubios-Chip (helle Schrift auf dunklem Grand).
    Methode:
      1. Dunklen Chip im Suchbereich lokalisieren (columns with Pixel < 80)
      2. Helle Text-Pixel innerhalb des Chips isolieren (Pixel > 160)
      3. OCR auf vergrößertem, invertiertem Text-Crop
    """
    try:
        import pytesseract
        from PIL import Image
        import numpy as np

        row = arr[int(h * y1f):int(h * y2f), x_search_start:x_search_end]

        # Schritt 1: Chip per dunklen Pixeln finden
        dark = (row[:, :, 0] < 80) & (row[:, :, 1] < 80) & (row[:, :, 2] < 80)
        chip_cols = np.where(dark.any(axis=0))[0]
        if len(chip_cols) < 5:
            return None
        cx1 = max(0, chip_cols[0] - 5)
        cx2 = min(row.shape[1], chip_cols[-1] + 5)

        chip = row[:, cx1:cx2]
        gray = np.array(Image.fromarray(chip).convert("L"))

        # Schritt 2: Helle Text-Pixel innerhalb des dunklen Chips
        text_mask = (gray > 160).astype(np.uint8) * 255
        rows_on = np.any(text_mask > 0, axis=1)
        cols_on = np.any(text_mask > 0, axis=0)
        if not rows_on.any() or not cols_on.any():
            return None

        rmin, rmax = np.where(rows_on)[0][[0, -1]]
        cmin, cmax = np.where(cols_on)[0][[0, -1]]
        text_only = text_mask[rmin:rmax + 1, cmin:cmax + 1]

        # Schritt 3: OCR
        img_ocr = Image.fromarray(255 - text_only)
        img_ocr = img_ocr.resize((img_ocr.width * 6, img_ocr.height * 6), Image.NEAREST)
        padded = Image.new("L", (img_ocr.width + 40, img_ocr.height + 40), 255)
        padded.paste(img_ocr, (20, 20))

        best = ""
        for psm in ["7", "8", "13"]:
            t = pytesseract.image_to_string(
                padded, lang="eng",
                config=f"--psm {psm} --oem 1 -c tessedit_char_whitelist='-0123456789.'"
            ).strip()
            if t and len(t) > len(best):
                best = t

        clean = re.sub(r'[^-0-9.]', '', best)
        clean = re.sub(r'\.{2,}', '.', clean).lstrip('.')
        return float(clean) if clean and clean not in ('-', '.') else None
    except Exception:
        return None


def ocr_screenshot(path: Path) -> dict | None:
    """Führt OCR durch and extrahiert all Kubios-Resting-HRV-Werte."""
    try:
        import pytesseract
        from PIL import Image
        import numpy as np
    except ImportError:
        print(t("Fehler: pytesseract, numpy und Pillow benötigt.", "Error: pytesseract, numpy and Pillow required."))
        return None

    img = Image.open(path).convert("RGB")
    arr = np.array(img)
    w, h = img.size

    # Standard-OCR for tabellarische HRV-Parameter
    text_std = pytesseract.image_to_string(img, lang="eng")
    top_crop = img.crop((0, 0, w, int(h * 0.4)))
    text_top = pytesseract.image_to_string(top_crop, lang="eng", config="--psm 6")
    full = text_std + "\n" + text_top

    if not re.search(r'RESTING\s+HRV|HRV\s+PARAMETERS', full, re.IGNORECASE):
        print(t(f"  ⚠ Kein Kubios Resting-HRV-Screen erkannt: {path.name}",
                f"  ⚠ No Kubios Resting-HRV screen detected: {path.name}"))
        return None

    dt = _datum_aus_dateiname(path)

    readiness = _parse_int(
        text_top,
        r'(\d{1,3})\s*%\s*\n?\s*READINESS',
        r'READINESS.*?(\d{1,3})\s*%',
        r'(\d{1,3})\s*%',
    )
    hr      = _parse_float(full, r'Heart\s*rate\s+(\d+\.?\d*)\s*bpm',
                                  r'(\d+\.?\d*)\s*bpm\s+\d+\s*ms')
    rmssd   = _parse_float(full, r'RMSSD\s+(\d+\.?\d*)\s*ms',
                                  r'bpm\s+(\d+\.?\d*)\s*ms')
    mean_rr = _parse_float(full, r'Mean\s*RR\s+([\d.]+)\s*ms')
    sdnn    = _parse_float(full, r'SDNN\s+([\d.]+)\s*ms')
    sd1     = _parse_float(full, r'Poincar[eé]\s*SD1\s+([\d.]+)\s*ms')
    sd2     = _parse_float(full, r'Poincar[eé]\s*SD2\s+([\d.]+)\s*ms')
    stress  = _parse_float(full, r'Stress\s*index\s+([\d.]+)')
    resp    = _parse_float(full, r'Respiratory\s*rate\s+([\d.]+)')
    lf      = _parse_float(full, r'LF\s*power\s+([\d.]+)\s*ms')
    hf      = _parse_float(full, r'HF\s*power\s+([\d.]+)\s*ms')
    lf_nu   = _parse_float(full, r'LF\s*power\s*\(n\.u\.\)\s+([\d.]+)')
    hf_nu   = _parse_float(full, r'HF\s*power\s*\(n\.u\.\)\s+([\d.]+)')
    lf_hf   = _parse_float(full, r'LF/HF\s*ratio\s+([\d.]+)')
    phys_age = _parse_int(full, r'Physiological\s*age\s+(\d+)')

    # PNS/SNS-Indexwerte via Chip-Extraktion (dunkler Chip → helle Schrift)
    # PNS-Chip: ~35-41% Bildhöhe — Suchbereich: gesamte Breite
    # SNS-Chip: ~43-49% Bildhöhe — Suchbereich: gesamte Breite
    # Der Chip sitzt links bei negativen values, rechts bei positiven
    pns = _ocr_chip_value(arr, h, 0.35, 0.41, 0, w)
    sns = _ocr_chip_value(arr, h, 0.43, 0.49, 0, w)

    # Vorzeichen-Plausibilität: PNS-Index negativ = supprimiert
    if pns is not None and pns > 5:
        pns = -pns

    return {
        "datetime":          dt,
        "hr_bpm":            hr,
        "rmssd_ms":          rmssd,
        "mean_rr_ms":        mean_rr,
        "sdnn_ms":           sdnn,
        "sd1_ms":            sd1,
        "sd2_ms":            sd2,
        "stress_index":      stress,
        "resp_rate":         resp,
        "lf_power_ms2":      lf,
        "hf_power_ms2":      hf,
        "lf_nu":             lf_nu,
        "hf_nu":             hf_nu,
        "lf_hf_ratio":       lf_hf,
        "pns_index":         pns,
        "sns_index":         sns,
        "physiological_age": phys_age,
        "readiness_pct":     readiness,
        "source":            "kubios_mobile",
    }


def _klinisch(r: dict) -> str:
    """Kurze klinische Einordnung der Werte."""
    lines = [f"\n=== Kubios Resting HRV — {r['datetime'][:16]} ===\n"]

    hr = r.get("hr_bpm")
    if hr:
        flag = "⚠️  Ruhetachykardie" if hr >= 100 else ("↑ erhöht" if hr >= 90 else "✓ normal")
        lines.append(f"  HR:           {hr:.0f} bpm  {flag}")

    rmssd = r.get("rmssd_ms")
    if rmssd:
        flag = "⚠️  stark erniedrigt" if rmssd < 15 else ("↓ niedrig" if rmssd < 25 else "✓ normal")
        lines.append(f"  RMSSD:        {rmssd:.1f} ms   {flag}")

    sdnn = r.get("sdnn_ms")
    if sdnn:
        flag = "⚠️  stark erniedrigt" if sdnn < 20 else ("↓ niedrig" if sdnn < 40 else "✓ normal")
        lines.append(f"  SDNN:         {sdnn:.2f} ms   {flag}")

    stress = r.get("stress_index")
    if stress:
        flag = "⚠️  sehr hoch" if stress > 20 else ("↑ erhöht" if stress > 10 else "✓ normal")
        lines.append(f"  Stress-Index: {stress:.2f}     {flag}")

    pns = r.get("pns_index")
    if pns is not None:
        flag = "⚠️  stark supprimiert" if pns < -1.5 else ("↓ niedrig" if pns < 0 else "✓ normal")
        lines.append(f"  PNS-Index:    {pns:+.2f}    {flag}")

    sns = r.get("sns_index")
    if sns is not None:
        flag = "⚠️  stark erhöht" if sns > 4 else ("↑ erhöht" if sns > 1 else "✓ normal")
        lines.append(f"  SNS-Index:    {sns:+.2f}    {flag}")

    readiness = r.get("readiness_pct")
    if readiness:
        flag = "⚠️  sehr niedrig" if readiness < 50 else ("↓ niedrig" if readiness < 65 else "✓ ok")
        lines.append(f"  Readiness:    {readiness}%        {flag}")

    resp = r.get("resp_rate")
    if resp:
        flag = "↑ erhöht" if resp > 20 else "✓ normal"
        lines.append(f"  Atemfrequenz: {resp:.1f} /min  {flag}")

    return "\n".join(lines)


def _save(conn, r: dict, dry_run: bool = False, update: bool = False) -> bool:
    existing = conn.execute(
        "SELECT datetime FROM kubios_hrv_resting WHERE datetime = ? AND person = ?",
        (r["datetime"], OWN_PERSON_ID)
    ).fetchone()
    if existing and not update:
        print(t(f"  ↺ Bereits vorhanden: {r['datetime'][:16]} — übersprungen (--update zum Überschreiben)",
                f"  ↺ Already exists: {r['datetime'][:16]} — skipped (use --update to overwrite)"))
        return False
    if existing and update:
        if dry_run:
            print(t(f"  [DRY-UPDATE] {r['datetime'][:16]}  PNS={r.get('pns_index')}  SNS={r.get('sns_index')}",
                    f"  [DRY-UPDATE] {r['datetime'][:16]}  PNS={r.get('pns_index')}  SNS={r.get('sns_index')}"))
            return True
        conn.execute(
            "UPDATE kubios_hrv_resting SET"
            "  hr_bpm=?, rmssd_ms=?, mean_rr_ms=?, sdnn_ms=?, sd1_ms=?, sd2_ms=?,"
            "  stress_index=?, resp_rate=?, lf_power_ms2=?, hf_power_ms2=?,"
            "  lf_nu=?, hf_nu=?, lf_hf_ratio=?, pns_index=?, sns_index=?,"
            "  physiological_age=?, readiness_pct=?, source=?"
            " WHERE datetime=? AND person=?",
            (
                r.get("hr_bpm"), r.get("rmssd_ms"), r.get("mean_rr_ms"),
                r.get("sdnn_ms"), r.get("sd1_ms"), r.get("sd2_ms"), r.get("stress_index"),
                r.get("resp_rate"), r.get("lf_power_ms2"), r.get("hf_power_ms2"),
                r.get("lf_nu"), r.get("hf_nu"), r.get("lf_hf_ratio"),
                r.get("pns_index"), r.get("sns_index"), r.get("physiological_age"),
                r.get("readiness_pct"), r["source"],
                r["datetime"], OWN_PERSON_ID,
            )
        )
        conn.commit()
        print(t(f"  ✓ Aktualisiert: {r['datetime'][:16]}  PNS={r.get('pns_index')}  SNS={r.get('sns_index')}",
                f"  ✓ Updated: {r['datetime'][:16]}  PNS={r.get('pns_index')}  SNS={r.get('sns_index')}"))
        return True

    if dry_run:
        print(t(f"  [DRY] {r['datetime'][:16]}  HR={r.get('hr_bpm')} bpm  "
                f"RMSSD={r.get('rmssd_ms')} ms  Stress={r.get('stress_index')}",
                f"  [DRY] {r['datetime'][:16]}  HR={r.get('hr_bpm')} bpm  "
                f"RMSSD={r.get('rmssd_ms')} ms  Stress={r.get('stress_index')}"))
        return True

    conn.execute("""
        INSERT INTO kubios_hrv_resting
          (datetime, hr_bpm, rmssd_ms, mean_rr_ms, sdnn_ms, sd1_ms, sd2_ms,
           stress_index, resp_rate, lf_power_ms2, hf_power_ms2, lf_nu, hf_nu,
           lf_hf_ratio, pns_index, sns_index, physiological_age, readiness_pct,
           source, person)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        r["datetime"], r.get("hr_bpm"), r.get("rmssd_ms"), r.get("mean_rr_ms"),
        r.get("sdnn_ms"), r.get("sd1_ms"), r.get("sd2_ms"), r.get("stress_index"),
        r.get("resp_rate"), r.get("lf_power_ms2"), r.get("hf_power_ms2"),
        r.get("lf_nu"), r.get("hf_nu"), r.get("lf_hf_ratio"),
        r.get("pns_index"), r.get("sns_index"), r.get("physiological_age"),
        r.get("readiness_pct"), r["source"], OWN_PERSON_ID
    ))
    conn.commit()
    print(t(f"  ✓ {r['datetime'][:16]}  HR={r.get('hr_bpm')} bpm  "
            f"RMSSD={r.get('rmssd_ms')} ms  Stress={r.get('stress_index')}",
            f"  ✓ {r['datetime'][:16]}  HR={r.get('hr_bpm')} bpm  "
            f"RMSSD={r.get('rmssd_ms')} ms  Stress={r.get('stress_index')}"))
    return True


def main():
    parser = argparse.ArgumentParser(
        description=t("Kubios HRV Screenshots importieren", "Import Kubios HRV screenshots"))
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument("--file", metavar="PNG",    help=t("Einzelner Screenshot", "Single screenshot"))
    group.add_argument("--dir",  metavar="ORDNER", help=t("Ordner mit Screenshots (Standard: imports/kubios/)",
                                                           "Folder with screenshots (default: imports/kubios/)"))
    parser.add_argument("--dry-run", action="store_true",
                        help=t("Vorschau ohne DB-Schreibzugriff", "Preview without DB writes"))
    parser.add_argument("--update", action="store_true",
                        help=t("Vorhandene Einträge überschreiben (z. B. PNS/SNS nachliefern)",
                               "Overwrite existing entries (e.g. to add PNS/SNS later)"))
    add_lang_arg(parser)

    args = parser.parse_args()
    apply_lang_from_args(args)

    conn = open_db()

    paths = []
    if args.file:
        paths = [Path(args.file)]
    else:
        d = Path(args.dir) if args.dir else _cfg.kubios_dir
        paths = sorted(d.glob("*.png")) + sorted(d.glob("*.PNG"))
        print(t(f"Ordner: {d}  |  Gefundene PNGs: {len(paths)}",
                f"Folder: {d}  |  PNGs found: {len(paths)}"))

    neu = 0
    for p in paths:
        print(t(f"\n→ {p.name}", f"\n→ {p.name}"))
        r = ocr_screenshot(p)
        if r:
            print(_klinisch(r))
            if _save(conn, r, dry_run=args.dry_run, update=args.update):
                neu += 1

    if not args.dry_run:
        log_import(conn, 'kubios_screenshot',
                   str(args.file) if args.file else str(args.dir or _cfg.kubios_dir), neu)
        conn.commit()
    conn.close()

    if args.dry_run:
        print(t(f"\nDRY-RUN: {neu} Einträge würden importiert.",
                f"\nDRY-RUN: {neu} entries would be imported."))
    else:
        print(t(f"\n{neu} Einträge neu importiert.",
                f"\n{neu} entries newly imported."))
        if neu > 0:
            print(t("Verlauf: python analyse/analyse_kubios_hrv.py --plot",
                    "History: python analyse/analyse_kubios_hrv.py --plot"))


if __name__ == "__main__":
    main()
