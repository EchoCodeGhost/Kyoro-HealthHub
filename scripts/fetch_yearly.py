#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Yearly Fetch — lädt Referenzdaten von externen Quellen und speichert sie lokal.

Dieses Script wird einmal jährlich ausgeführt (manuell oder per Cron/Schedule-Skill)
und lädt regulatorische Referenztabellen herunter, die für die Inhaltsstoff-Analyse
benötigt werden (ECHA-SVHC, CosIng).

@tier        infrastructure
@purpose.de  Lädt ECHA-SVHC-Kandidatenliste (chronische Risikostoffe: Karzinogene, Mutagene,
             Reproduktionstoxizität, endokrine Disruptoren) und CosIng-Annex-Daten
             (in der EU verbotene/beschränkte Kosmetik-Inhaltsstoffe) als lokale CSV-Dateien.
             Ermöglicht Allergen-Matching ohne wiederholte Netzwerkabfragen und hält die
             Referenzdaten aktuell durch jährlichen Refresh.
@purpose.en  Downloads ECHA-SVHC candidate list (chronic risk substances: carcinogens,
             mutagens, reproductive toxicants, endocrine disruptors) and CosIng annex data
             (substances prohibited/restricted in EU cosmetics) as local CSV files.
             Enables allergen matching without repeated network requests and keeps
             reference data current through annual refresh.
@method.de   1. Lädt ECHA-SVHC-Kandidatenliste von ECHA-Website (CSV/Excel → CSV)
             2. Lädt CosIng Annex II (verbotene Substanzen) und Annex III (beschränkte Substanzen)
                von EU-Kommissions-Website
             3. Speichert alle Daten in data/reference/ (echa_svhc.csv, cosing_annex_ii.csv,
                cosing_annex_iii.csv)
             4. Aktualisiert manifest.json mit Datum des letzten Abrufs pro Quelle
             5. Jede Quelle wird unabhängig versucht; Fehler in einer Quelle brechen nicht
                den gesamten Prozess ab
@method.en   1. Downloads ECHA-SVHC candidate list from ECHA website (CSV/Excel → CSV)
             2. Downloads CosIng Annex II (prohibited substances) and Annex III (restricted
                substances) from EU Commission website
             3. Stores all data in data/reference/ (echa_svhc.csv, cosing_annex_ii.csv,
                cosing_annex_iii.csv)
             4. Updates manifest.json with last fetch date per source
             5. Each source is attempted independently; errors in one source don't break
                the entire process
@reads       ECHA-Website (https://echa.europa.eu), EU-Kommission CosIng-Daten
@writes      data/reference/echa_svhc.csv, data/reference/cosing_annex_ii.csv,
             data/reference/cosing_annex_iii.csv, data/reference/manifest.json
@limits.de   Abhängig von der Verfügbarkeit und dem Format der Downloadquellen.
             Quellen können ihr Format ändern; manuelle Anpassung der Parser nötig.
             Kein Live-Update — Referenzdaten werden nur durch erneuten Aufruf aktualisiert.

@relevance.de  Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung
@relevance.en  Provides health data functions, essential for medical data processing
@limits.en   Dependent on availability and format of download sources.
             Sources may change their format; manual parser adjustment may be needed.
             No live update — reference data is only updated by re-running this script.
@usage
    python scripts/fetch_yearly.py
    python scripts/fetch_yearly.py --force
    python scripts/fetch_yearly.py --check
"""

import argparse
import csv
import json
import sys
import tempfile
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from health_config import Config as _Cfg
from modules.i18n import t, add_lang_arg, apply_lang_from_args

_REFERENCE_DIR = Path(__file__).parent / "data" / "reference"
_MANIFEST_FILE = _REFERENCE_DIR / "manifest.json"

# ECHA SVHC Candidate List URL (CSV format)
_ECHA_SVHC_URL = "https://echa.europa.eu/documents/10162/13632/svhc_candidate_list_en.csv"

# CosIng URLs - these may need to be updated as EU changes their hosting
# Annex II: List of substances prohibited in cosmetic products
_COSING_ANNEX_II_URL = "https://ec.europa.eu/growth/tools-databases/cosing/data/annex-ii-list-en.txt"
# Annex III: List of substances restricted in cosmetic products  
_COSING_ANNEX_III_URL = "https://ec.europa.eu/growth/tools-databases/cosing/data/annex-iii-list-en.txt"

# Fallback URLs if above don't work
_ECHA_SVHC_FALLBACK_URLS = [
    "https://echa.europa.eu/documents/10162/13632/svhc_candidate_list_en.csv",
    "https://echa.europa.eu/-/svhc-candidate-list",
]

# Minimum age in days before re-fetching (default: 365 days = 1 year)
_MIN_AGE_DAYS = 365


def _ok(file: str, source: str) -> dict:
    """Return success status for manifest."""
    return {
        "status": "ok",
        "source": source,
        "file": file,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


def _err(reason: str, source: str) -> dict:
    """Return error status for manifest."""
    return {
        "status": "error",
        "source": source,
        "reason": reason,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


def _skip(reason: str, source: str) -> dict:
    """Return skip status for manifest."""
    return {
        "status": "skipped",
        "source": source,
        "reason": reason,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


def _load_manifest() -> dict:
    """Load the manifest file or return empty dict."""
    if _MANIFEST_FILE.exists():
        try:
            return json.loads(_MANIFEST_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_manifest(manifest: dict) -> None:
    """Save the manifest file."""
    _MANIFEST_FILE.parent.mkdir(parents=True, exist_ok=True)
    _MANIFEST_FILE.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )


def _should_fetch(source: str, manifest: dict, force: bool = False) -> bool:
    """Check if a source should be fetched based on manifest age."""
    if force:
        return True
    
    entry = manifest.get(source, {})
    fetched_at = entry.get("fetched_at")
    
    if not fetched_at:
        return True
    
    try:
        fetch_time = datetime.fromisoformat(fetched_at.replace("Z", "+00:00"))
        age = (datetime.now(timezone.utc) - fetch_time).days
        return age >= _MIN_AGE_DAYS
    except Exception:
        return True


def _download_url(url: str, timeout: int = 30) -> bytes | None:
    """Download content from a URL."""
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "KyoroHealthHub/1.0"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except Exception as e:
        print(f"[fetch_yearly] Download fehlgeschlagen: {url} - {e}", file=sys.stderr)
        return None


def _parse_echa_svhc(csv_content: bytes) -> list[dict]:
    """Parse ECHA SVHC CSV content into a list of dicts."""
    try:
        content = csv_content.decode("utf-8-sig")  # Handle BOM
        reader = csv.DictReader(content.splitlines())
        result = []
        for row in reader:
            # Clean and normalize keys
            clean_row = {k.strip(): v.strip() for k, v in row.items()}
            # Extract substance name from various possible columns
            name = clean_row.get("Substance", clean_row.get("Substance name", clean_row.get("Name", "")))
            if name:
                result.append({
                    "Substance": name,
                    "CAS": clean_row.get("CAS", clean_row.get("CAS No", "")),
                    "EC": clean_row.get("EC", clean_row.get("EC No", "")),
                    "Category": clean_row.get("Category", clean_row.get("Reason for inclusion", "")),
                    "Risk": clean_row.get("Risk", ""),
                    "Date_of_inclusion": clean_row.get("Date of inclusion", ""),
                })
        return result
    except Exception as e:
        print(f"[fetch_yearly] ECHA-SVHC Parsing-Fehler: {e}", file=sys.stderr)
        return []


def _parse_cosing_text(text_content: bytes) -> list[dict]:
    """Parse CosIng text file (space/tab-separated) into a list of dicts."""
    try:
        content = text_content.decode("utf-8-sig")
        lines = content.splitlines()
        result = []
        for line in lines[1:]:  # Skip header
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # CosIng files are typically tab or multi-space separated
            parts = line.split()
            if len(parts) >= 2:
                result.append({
                    "INCI": parts[0],
                    "CAS": parts[1] if len(parts) > 1 else "",
                    "Status": "Prohibited",
                    "Restriction": " ".join(parts[2:]) if len(parts) > 2 else "",
                })
        return result
    except Exception as e:
        print(f"[fetch_yearly] CosIng Parsing-Fehler: {e}", file=sys.stderr)
        return []


def fetch_echa_svhc(force: bool = False) -> dict:
    """
    Download ECHA SVHC candidate list.
    
    Returns status dict for manifest.
    """
    if not force and not _should_fetch("echa_svhc", _load_manifest(), force):
        return _skip("Letzter Abruf < 1 Jahr alt", "echa_svhc")
    
    # Try all URLs
    for url in _ECHA_SVHC_FALLBACK_URLS:
        content = _download_url(url)
        if content:
            data = _parse_echa_svhc(content)
            if data:
                # Save to CSV
                _REFERENCE_DIR.mkdir(parents=True, exist_ok=True)
                output_file = _REFERENCE_DIR / "echa_svhc.csv"
                with open(output_file, "w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=["Substance", "CAS", "EC", "Category", "Risk", "Date_of_inclusion"])
                    writer.writeheader()
                    writer.writerows(data)
                print(f"[fetch_yearly] ECHA-SVHC: {len(data)} Einträge gespeichert in {output_file}")
                return _ok("echa_svhc.csv", "echa_svhc")
    
    return _err("Alle ECHA-SVHC-URLs fehlgeschlagen", "echa_svhc")


def fetch_cosing_annex_ii(force: bool = False) -> dict:
    """
    Download CosIng Annex II (prohibited substances).
    
    Returns status dict for manifest.
    """
    if not force and not _should_fetch("cosing_annex_ii", _load_manifest(), force):
        return _skip("Letzter Abruf < 1 Jahr alt", "cosing_annex_ii")
    
    content = _download_url(_COSING_ANNEX_II_URL)
    if not content:
        return _err(f"Download fehlgeschlagen: {_COSING_ANNEX_II_URL}", "cosing_annex_ii")
    
    data = _parse_cosing_text(content)
    if not data:
        return _err("Keine Daten geparst", "cosing_annex_ii")
    
    # Save to CSV
    _REFERENCE_DIR.mkdir(parents=True, exist_ok=True)
    output_file = _REFERENCE_DIR / "cosing_annex_ii.csv"
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["INCI", "CAS", "Status", "Restriction"])
        writer.writeheader()
        writer.writerows(data)
    
    print(f"[fetch_yearly] CosIng Annex II: {len(data)} Einträge gespeichert in {output_file}")
    return _ok("cosing_annex_ii.csv", "cosing_annex_ii")


def fetch_cosing_annex_iii(force: bool = False) -> dict:
    """
    Download CosIng Annex III (restricted substances).
    
    Returns status dict for manifest.
    """
    if not force and not _should_fetch("cosing_annex_iii", _load_manifest(), force):
        return _skip("Letzter Abruf < 1 Jahr alt", "cosing_annex_iii")
    
    content = _download_url(_COSING_ANNEX_III_URL)
    if not content:
        return _err(f"Download fehlgeschlagen: {_COSING_ANNEX_III_URL}", "cosing_annex_iii")
    
    data = _parse_cosing_text(content)
    if not data:
        return _err("Keine Daten geparst", "cosing_annex_iii")
    
    # Save to CSV
    _REFERENCE_DIR.mkdir(parents=True, exist_ok=True)
    output_file = _REFERENCE_DIR / "cosing_annex_iii.csv"
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["INCI", "CAS", "Status", "Restriction"])
        writer.writeheader()
        writer.writerows(data)
    
    print(f"[fetch_yearly] CosIng Annex III: {len(data)} Einträge gespeichert in {output_file}")
    return _ok("cosing_annex_iii.csv", "cosing_annex_iii")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=t(
            "Lädt jährliche Referenzdaten (ECHA-SVHC, CosIng) für Inhaltsstoff-Analyse",
            "Downloads yearly reference data (ECHA-SVHC, CosIng) for ingredient analysis",
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--force", action="store_true",
                        help=t("Refresh erzwingen, auch wenn <1 Jahr alt",
                              "Force refresh even if <1 year old"))
    parser.add_argument("--check", action="store_true",
                        help=t("Nur Status prüfen, nicht herunterladen",
                              "Only check status, don't download"))
    parser.add_argument("--echa-only", action="store_true",
                        help=t("Nur ECHA-SVHC herunterladen",
                              "Only download ECHA-SVHC"))
    parser.add_argument("--cosing-only", action="store_true",
                        help=t("Nur CosIng herunterladen",
                              "Only download CosIng"))
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)

    manifest = _load_manifest()
    results = {}

    # ECHA-SVHC
    if not args.cosing_only:
        if args.check:
            if _should_fetch("echa_svhc", manifest, args.force):
                print(t("ECHA-SVHC: Sollte aktualisiert werden (letzter Abruf > 1 Jahr)",
                      "ECHA-SVHC: Should be updated (last fetch > 1 year)"))
            else:
                print(t("ECHA-SVHC: Aktuell (letzter Abruf < 1 Jahr)",
                      "ECHA-SVHC: Current (last fetch < 1 year)"))
        else:
            result = fetch_echa_svhc(args.force)
            results["echa_svhc"] = result
            manifest["echa_svhc"] = result

    # CosIng Annex II
    if not args.echa_only:
        if args.check:
            if _should_fetch("cosing_annex_ii", manifest, args.force):
                print(t("CosIng Annex II: Sollte aktualisiert werden",
                      "CosIng Annex II: Should be updated"))
            else:
                print(t("CosIng Annex II: Aktuell",
                      "CosIng Annex II: Current"))
        else:
            result = fetch_cosing_annex_ii(args.force)
            results["cosing_annex_ii"] = result
            manifest["cosing_annex_ii"] = result

    # CosIng Annex III
    if not args.echa_only:
        if args.check:
            if _should_fetch("cosing_annex_iii", manifest, args.force):
                print(t("CosIng Annex III: Sollte aktualisiert werden",
                      "CosIng Annex III: Should be updated"))
            else:
                print(t("CosIng Annex III: Aktuell",
                      "CosIng Annex III: Current"))
        else:
            result = fetch_cosing_annex_iii(args.force)
            results["cosing_annex_iii"] = result
            manifest["cosing_annex_iii"] = result

    # Save manifest
    if not args.check:
        _save_manifest(manifest)
        print(f"\n[fetch_yearly] Manifest gespeichert: {_MANIFEST_FILE}")
        
        # Summary
        print("\n" + "=" * 60)
        print(t("Zusammenfassung:", "Summary:"))
        for source, result in results.items():
            status = result.get("status", "unknown")
            status_de = {"ok": "✓ OK", "error": "✗ FEHLER", "skipped": "⊘ ÜBERSPRUNGEN"}.get(status, status)
            status_en = {"ok": "✓ OK", "error": "✗ ERROR", "skipped": "⊘ SKIPPED"}.get(status, status)
            print(f"  {source}: {t(status_de, status_en)}")
            if status == "error":
                print(f"    Reason: {result.get('reason', 'Unknown')}")
        print("=" * 60)


if __name__ == "__main__":
    main()
