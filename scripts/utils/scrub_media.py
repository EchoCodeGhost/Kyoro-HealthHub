#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
scrub_media.py — Metadaten, Adressen, Namen, Nummern und Orte aus Bildern und PDFs melden oder entfernen

@tier        infrastructure
@purpose.de  Kommandozeile für modules.media_redaction: zeigt, welche Metadaten (EXIF, GPS, PDF-Info,
             XMP, Anhänge, JavaScript) und welche Adressen, Namen, Telefon- und Versichertennummern, Koordinaten und persönlichen Ortsnamen
             in Dateien stecken, und schreibt
             bereinigte Kopien. Alles lokal, Originale bleiben unverändert.
@purpose.en  Command line for modules.media_redaction: shows which metadata (EXIF, GPS, PDF info,
             XMP, attachments, JavaScript) and which addresses and names are in files, and writes cleaned
             copies. All local, originals stay unchanged.
@method.de   Unterbefehle: report (Metadaten anzeigen, optional als JSON exportieren), scrub (eine
             Datei bereinigen), scrub-dir (Ordner rekursiv in einen Zielordner), check (Exit-Code 1,
             wenn Metadaten, Adressen oder Namen gefunden werden). Werte werden nur mit --show-values
             ausgegeben. Adressen, Namen, Nummern und Orte werden nie im Klartext gemeldet, nur als Anzahl.
@method.en   Subcommands: report (show metadata, optionally export as JSON), scrub (clean one
             file), scrub-dir (folder recursively into a target folder), check (exit code 1 if
             metadata, addresses or names are found). Values are only printed with --show-values.
             Addresses are never reported in cleartext, only as a count.
@reads       Bild- und PDF-Dateien, ~/.config/kyoro/health_config.json (optional)
@writes      Bereinigte Kopien am Zielort, optional JSON-Report (--json-out)
@limits.de   Überschreibt nie das Original (Ziel muss ein anderer Pfad sein). Ohne OCR/poppler
             wird nur die Metadaten-Bereinigung ausgeführt und eine Warnung ausgegeben.
             Exit-Codes: 0 sauber, 1 Funde, 2 Werkzeuge fehlen oder Fehler (mit --strict).
@relevance.de  Macht Bild- und PDF-Bereinigung ohne Import nutzbar, etwa vor dem Teilen von Dateien
@relevance.en  Makes image and PDF cleaning usable without an import, e.g. before sharing files
@limits.en   Never overwrites the original (target must be a different path). Without
             OCR/poppler only metadata removal runs and a warning is printed. Exit codes:
             0 clean, 1 findings, 2 tools missing or error (with --strict).
@usage
    python -m utils.scrub_media report befund.pdf foto.jpg
    python -m utils.scrub_media report ordner/ --json-out report.json
    python -m utils.scrub_media scrub befund.pdf sauber/befund.pdf
    python -m utils.scrub_media scrub-dir eingang/ ausgang/ --strict
    python -m utils.scrub_media check ordner/
    python -m utils.scrub_media scrub foto.jpg out.jpg --address "Musterstraße 12, 12345 Musterstadt" --name "Erika Mustermann"
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modules import media_redaction as mr


def _files(paths: list[Path]) -> list[Path]:
    out: list[Path] = []
    for p in paths:
        if p.is_dir():
            out += sorted(f for f in p.rglob("*")
                          if f.is_file() and (f.suffix.lower() == ".pdf" or f.suffix.lower() in mr.IMAGE_EXTS))
        elif p.is_file():
            out.append(p)
    return out


def _report(path: Path, show_values: bool, extra: list[str], names: list[str],
            places: list[str]) -> dict:
    try:
        if path.suffix.lower() == ".pdf":
            return mr.report_pdf(path, show_values, extra, names, places)
        return mr.report_image(path, show_values)
    except Exception as exc:
        return {"file": path.name, "error": f"{type(exc).__name__}: {exc}"}


def _has_findings(info: dict) -> bool:
    if "error" in info:
        return False
    if info["type"] == "pdf":
        return bool(info["findings"])
    return bool(info["pii_tags"] or info["has_gps"] or info["other_metadata"])


def _print_report(info: dict) -> None:
    if "error" in info:
        print(f"{info['file']}: FEHLER {info['error']}")
        return
    if info["type"] == "pdf":
        print(f"{info['file']}: PDF, {info['pages']} Seite(n)")
        print(f"  Info: {', '.join(info['info_keys']) or '-'} | XMP: {', '.join(info['xmp_keys']) or '-'}")
        print(f"  Anhänge: {info['embedded_files']} | JavaScript: {info['javascript']} | "
              f"OpenAction: {info['open_action']} | Formularfelder: {info['form_fields']} | "
              f"Annotationen: {info['annotations']} (Links: {info['link_uris']})")
        print(f"  Bilder: {info['images']} (mit GPS: {info['images_with_gps']}) | "
              f"Textebene: {info['text_chars']} Zeichen | Adressen in Textebene: {info['addresses_in_text_layer']} | "
              f"Namen: {info['names_in_text_layer']} | "
              f"Telefon-/Versichertennr.: {info['identifiers_in_text_layer']} | "
              f"Orte/Koordinaten: {info['places_in_text_layer']}")
        if not info["has_text_layer"]:
            print("  Hinweis: Scan ohne Textebene, Adressen im Bild nur per OCR prüfbar (scrub)")
    else:
        print(f"{info['file']}: Bild {info.get('format')} {info.get('size')}")
        print(f"  EXIF: {len(info['exif_tags'])} Tag(s) | PII-Tags: {', '.join(info['pii_tags']) or '-'} | "
              f"GPS: {info['has_gps']} | weitere: {', '.join(info['other_metadata']) or '-'}")
    for key in ("values", "info_values"):
        if key in info:
            for k, v in info[key].items():
                print(f"    {k} = {v}")


def _scrub_one(src: Path, dst: Path, args) -> mr.RedactionResult:
    kw = dict(redact_addresses=not args.no_redact_addresses, extra_addresses=args.address, ocr=args.ocr,
              redact_names=not args.no_redact_names, extra_names=args.name,
              redact_identifiers=not args.no_redact_ids,
              redact_locations=not args.no_redact_places, extra_places=args.place)
    if src.suffix.lower() == ".pdf":
        return mr.scrub_pdf_full(src, dst, dpi=args.dpi, **kw)
    return mr.scrub_image(src, dst, **kw)


def _print_result(src: Path, dst: Path, res: mr.RedactionResult) -> None:
    print(f"{src.name} -> {dst}: {res.addresses} Adresse(n), {res.names} Name(n), "
          f"{res.identifiers} Telefon-/Versichertennr., {res.places} Ort(e)/Koordinaten geschwärzt, "
          f"{res.pages_redacted} Seite(n)/Bild ersetzt, {res.images_scrubbed} eingebettete(s) Bild(er) bereinigt, "
          f"{len(res.locations)} GPS-Fund(e) entfernt, Rest: {res.residual}")
    for w in res.warnings:
        print(f"  ⚠ {w}")


def _finish(results: list[mr.RedactionResult], strict: bool) -> int:
    if strict and any(r.warnings or r.residual for r in results):
        return 2
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    sub = parser.add_subparsers(dest="cmd", required=True)

    def common(p, scrub: bool):
        p.add_argument("--address", action="append", default=[],
                       help="Zusätzliche bekannte Adresse (mehrfach möglich)")
        p.add_argument("--name", action="append", default=[],
                       help="Zusätzlicher bekannter Personenname (mehrfach möglich)")
        p.add_argument("--place", action="append", default=[],
                       help="Zusätzlicher persönlicher Ortsname (mehrfach möglich)")
        if scrub:
            p.add_argument("--no-redact-addresses", action="store_true", help="Adressen nicht schwärzen")
            p.add_argument("--no-redact-names", action="store_true", help="Namen nicht schwärzen")
            p.add_argument("--no-redact-ids", action="store_true",
                           help="Telefon- und Versichertennummern nicht schwärzen")
            p.add_argument("--no-redact-places", action="store_true",
                           help="GPS-Koordinaten und persönliche Ortsnamen nicht schwärzen")
            p.add_argument("--ocr", choices=["auto", "always", "never"], default="auto")
            p.add_argument("--dpi", type=int, default=200)
            p.add_argument("--strict", action="store_true", help="Exit 2 bei Warnung oder Rest-Fund")

    p = sub.add_parser("report", help="Metadaten anzeigen")
    p.add_argument("paths", nargs="+", type=Path)
    p.add_argument("--show-values", action="store_true", help="Metadaten-Werte ausgeben (enthält PII)")
    p.add_argument("--json-out", type=Path, help="Report als JSON schreiben")
    common(p, False)

    p = sub.add_parser("check", help="Exit 1, wenn Funde vorhanden")
    p.add_argument("paths", nargs="+", type=Path)
    common(p, False)

    p = sub.add_parser("scrub", help="Eine Datei bereinigen")
    p.add_argument("src", type=Path)
    p.add_argument("dst", type=Path)
    common(p, True)

    p = sub.add_parser("scrub-dir", help="Ordner rekursiv bereinigen")
    p.add_argument("src", type=Path)
    p.add_argument("dst", type=Path)
    common(p, True)

    args = parser.parse_args(argv)

    if args.cmd in ("report", "check"):
        infos = [_report(f, getattr(args, "show_values", False), args.address, args.name, args.place) for f in _files(args.paths)]
        if args.cmd == "report":
            for info in infos:
                _print_report(info)
            if args.json_out:
                args.json_out.write_text(json.dumps(infos, indent=2, ensure_ascii=False), encoding="utf-8")
                print(f"JSON-Report: {args.json_out}")
        found = [i for i in infos if _has_findings(i)]
        if args.cmd == "check":
            for i in found:
                print(f"Funde: {i['file']}")
            print(f"{len(found)} von {len(infos)} Datei(en) mit Funden")
        return 1 if found else 0

    if args.cmd == "scrub":
        if args.src.resolve() == args.dst.resolve():
            print("Ziel muss ein anderer Pfad als das Original sein", file=sys.stderr)
            return 2
        res = _scrub_one(args.src, args.dst, args)
        _print_result(args.src, args.dst, res)
        return _finish([res], args.strict)

    results = []
    for f in _files([args.src]):
        dst = args.dst / f.relative_to(args.src)
        if dst.resolve() == f.resolve():
            print("Zielordner darf nicht der Quellordner sein", file=sys.stderr)
            return 2
        try:
            res = _scrub_one(f, dst, args)
        except Exception as exc:
            print(f"{f.name}: FEHLER {type(exc).__name__}: {exc}", file=sys.stderr)
            results.append(mr.RedactionResult(warnings=[str(exc)]))
            continue
        _print_result(f, dst, res)
        results.append(res)
    return _finish(results, args.strict)


if __name__ == "__main__":
    raise SystemExit(main())
