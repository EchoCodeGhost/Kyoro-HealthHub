#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
md_to_pdf.py — Markdown-Dateien in PDF umwandeln (via pandoc + xelatex)

@tier        infrastructure
@purpose.de  Konvertiert eine oder mehrere Markdown-Dateien zu druckbaren PDFs.
             Optimiert für medizinische Berichte: saubere Typografie, Titelblock,
             Datum, Seitenzahlen, Querverweise.
@purpose.en  Converts one or more Markdown files to printable PDFs.
             Optimised for medical reports: clean typography, title block,
             date, page numbers, cross-references.
@method.de   Ruft pandoc mit xelatex-Engine auf. Schriftart, Ränder und Metadaten
             werden per YAML-Frontmatter oder CLI-Flags gesetzt.
             Ohne --title wird der Dateiname als Titel verwendet.
@method.en   Calls pandoc with xelatex engine. Font, margins and metadata are set
             via YAML front matter or CLI flags.
             Without --title the filename is used as title.
@reads       Markdown-Datei(en) (.md)
@writes      PDF-Datei(en) (neben der Quelldatei oder in --out-dir)
@limits.de   Benötigt pandoc ≥ 2.x und xelatex (texlive).
             Sehr lange Tabellen können über Seitenränder laufen — ggf. --landscape nutzen.

@relevance.de  Bietet Hilfsfunktionen für die Datenverarbeitung, essentiell für die Systemfunktionalität
@relevance.en  Provides utility functions for data processing, essential for system functionality
@limits.en   Requires pandoc ≥ 2.x and xelatex (texlive).
             Very wide tables may overflow margins — use --landscape if needed.
@usage
    python3 scripts/utils/md_to_pdf.py bericht.md
    python3 scripts/utils/md_to_pdf.py analyses/manual/lab_verlauf_*.md
    python3 scripts/utils/md_to_pdf.py bericht.md --out-dir exports/
    python3 scripts/utils/md_to_pdf.py bericht.md --title "Labor-Befunde" --author "Kyoro"
    python3 scripts/utils/md_to_pdf.py bericht.md --landscape
    python3 scripts/utils/md_to_pdf.py bericht.md --font-size 10
"""

import argparse
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.i18n import t, add_lang_arg, apply_lang_from_args

# ── pandoc-Defaults ───────────────────────────────────────────────────────────

_FONT       = "DejaVu Sans"       # breite Unicode-Abdeckung, inkl. ↑↓⚠🟢🟡🔴 via Fallback
_FONT_MONO  = "DejaVu Sans Mono"
_FONT_SIZE  = 11                  # pt
_MARGIN     = "2cm"
_ENGINE     = "xelatex"

# LaTeX-Header: Seitenzahlen + kompakte Listen
_LATEX_HEADER = r"""
\usepackage{fancyhdr}
\pagestyle{fancy}
\fancyhf{}
\fancyfoot[C]{\thepage}
\renewcommand{\headrulewidth}{0pt}
\usepackage{booktabs}
\usepackage{longtable}
\usepackage{array}
\setlength{\parindent}{0pt}
\setlength{\parskip}{4pt}
"""

# Emoji-Fallback via Noto Color Emoji (falls vorhanden)
_EMOJI_LATEX = r"""
\usepackage{fontspec}
\newfontfamily\emojifont{Noto Color Emoji}[Renderer=Harfbuzz]
"""


def _noto_emoji_available() -> bool:
    result = subprocess.run(
        ["fc-list", ":family=Noto Color Emoji"],
        capture_output=True, text=True
    )
    return bool(result.stdout.strip())


def _build_pandoc_cmd(src: Path, dst: Path, title: str, author: str,
                      date_str: str, font_size: int, landscape: bool,
                      toc: bool) -> list[str]:
    header_includes = _LATEX_HEADER
    if _noto_emoji_available():
        header_includes += _EMOJI_LATEX

    cmd = [
        "pandoc",
        str(src),
        "-o", str(dst),
        f"--pdf-engine={_ENGINE}",
        "--from=markdown+pipe_tables+fenced_code_blocks+smart",
        "-V", f"mainfont={_FONT}",
        "-V", f"monofont={_FONT_MONO}",
        "-V", f"fontsize={font_size}pt",
        "-V", f"geometry:margin={_MARGIN}",
        "-V", f"geometry:{'landscape,' if landscape else ''}a4paper",
        "-V", "colorlinks=true",
        "-V", "linkcolor=NavyBlue",
        "-V", f"header-includes={_LATEX_HEADER}",
        "--highlight-style=tango",
    ]

    if title:
        cmd += ["-V", f"title={title}"]
    if author:
        cmd += ["-V", f"author={author}"]
    if date_str:
        cmd += ["-V", f"date={date_str}"]
    if toc:
        cmd += ["--toc", "--toc-depth=3"]

    return cmd


def convert(src: Path, out_dir: Path | None, title: str, author: str,
            date_str: str, font_size: int, landscape: bool, toc: bool,
            verbose: bool) -> bool:
    dst_dir = out_dir if out_dir else src.parent
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / (src.stem + ".pdf")

    effective_title = title or src.stem.replace("_", " ").replace("-", " ")

    cmd = _build_pandoc_cmd(src, dst, effective_title, author,
                            date_str, font_size, landscape, toc)

    if verbose:
        print("  " + " ".join(cmd))

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(t(f"  ✗ Fehler bei {src.name}:", f"  ✗ Error in {src.name}:"),
              file=sys.stderr)
        # Nur relevante LaTeX-Zeilen ausgeben, nicht alles
        for line in result.stderr.splitlines():
            if any(k in line for k in ("Error", "error", "!", "LaTeX", "Warning")):
                print(f"    {line}", file=sys.stderr)
        return False

    size_kb = dst.stat().st_size // 1024
    print(t(f"  ✓ {dst}  ({size_kb} KB)", f"  ✓ {dst}  ({size_kb} KB)"))
    return True


# ── Hauptfunktion ─────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(
        description=t("Markdown → PDF via pandoc/xelatex",
                      "Markdown → PDF via pandoc/xelatex")
    )
    ap.add_argument("files", nargs="+", metavar="DATEI.md",
                    help=t("Eine oder mehrere Markdown-Dateien (Glob möglich)",
                           "One or more Markdown files (glob supported)"))
    ap.add_argument("--out-dir", metavar="VERZ", default=None,
                    help=t("Ausgabeverzeichnis (Standard: neben der Quelldatei)",
                           "Output directory (default: next to source file)"))
    ap.add_argument("--title", default="",
                    help=t("Titel (Standard: Dateiname)", "Title (default: filename)"))
    ap.add_argument("--author", default="Kyoro-HealthHub",
                    help=t("Autor (Standard: Kyoro-HealthHub)",
                           "Author (default: Kyoro-HealthHub)"))
    ap.add_argument("--date", dest="date_str", default=date.today().isoformat(),
                    help=t("Datum (Standard: heute, YYYY-MM-DD)",
                           "Date (default: today, YYYY-MM-DD)"))
    ap.add_argument("--font-size", type=int, default=_FONT_SIZE, metavar="PT",
                    help=t(f"Schriftgröße in pt (Standard: {_FONT_SIZE})",
                           f"Font size in pt (default: {_FONT_SIZE})"))
    ap.add_argument("--landscape", action="store_true",
                    help=t("Querformat (für breite Tabellen)",
                           "Landscape orientation (for wide tables)"))
    ap.add_argument("--toc", action="store_true",
                    help=t("Inhaltsverzeichnis einfügen", "Insert table of contents"))
    ap.add_argument("--verbose", action="store_true",
                    help=t("pandoc-Befehl anzeigen", "Show pandoc command"))
    add_lang_arg(ap)
    args = ap.parse_args()
    apply_lang_from_args(args)

    out_dir = Path(args.out_dir) if args.out_dir else None

    paths: list[Path] = []
    for f in args.files:
        p = Path(f)
        if not p.exists():
            print(t(f"Nicht gefunden: {p}", f"Not found: {p}"), file=sys.stderr)
            continue
        if p.suffix.lower() != ".md":
            print(t(f"Übersprungen (kein .md): {p}", f"Skipped (not .md): {p}"),
                  file=sys.stderr)
            continue
        paths.append(p)

    if not paths:
        print(t("Keine gültigen Markdown-Dateien angegeben.",
                "No valid Markdown files specified."), file=sys.stderr)
        sys.exit(1)

    ok = err = 0
    for p in paths:
        if len(paths) > 1:
            print(t(f"Konvertiere {p.name} …", f"Converting {p.name} …"))
        success = convert(p, out_dir, args.title if len(paths) == 1 else "",
                          args.author, args.date_str, args.font_size,
                          args.landscape, args.toc, args.verbose)
        if success:
            ok += 1
        else:
            err += 1

    if len(paths) > 1:
        print(t(f"\n{ok} konvertiert, {err} Fehler.",
                f"\n{ok} converted, {err} errors."))

    sys.exit(1 if err and not ok else 0)


if __name__ == "__main__":
    main()
