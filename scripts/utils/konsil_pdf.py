# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
konsil_pdf.py — Konsil-Gutachten als PDF rendern

@tier        infrastructure
@purpose.de  Rendert die Markdown-Gutachten eines Konsil-Laufs zu druckfertigen
             PDFs: ein Sammelband mit Deckblatt und Inhaltsverzeichnis sowie ein
             Einzel-PDF je Gutachten.
@purpose.en  Renders the markdown assessments of a consultation run into
             print-ready PDFs: one combined volume with cover page and table of
             contents, plus one PDF per individual assessment.
@method.de   Markdown -> HTML (python-markdown, Tabellen-Extension) -> PDF via
             Chrome im Headless-Modus (--print-to-pdf). Chrome ist auf macOS
             ohnehin vorhanden; damit entfaellt eine LaTeX-/wkhtmltopdf-
             Abhaengigkeit. Seitenumbrueche zwischen Gutachten per CSS.
@method.en   Markdown -> HTML (python-markdown, tables extension) -> PDF via
             headless Chrome (--print-to-pdf). Chrome already exists on macOS,
             so no LaTeX/wkhtmltopdf dependency is needed. Page breaks between
             assessments via CSS.
@reads       analyses/<datum>/konsil/*.md
@writes      analyses/<datum>/konsil/pdf/*.pdf
@relevance.de  Ermöglicht die druckfertige Weitergabe von Konsil-Gutachten an Ärzte, essentiell für die Arztkommunikation
@relevance.en  Enables print-ready hand-off of consultation assessments to physicians, essential for clinician communication
@limits.de   Braucht Google Chrome an einem der bekannten Pfade. Ohne Chrome
             wird das HTML trotzdem geschrieben und der Pfad gemeldet, damit
             manuell gedruckt werden kann.
@limits.en   Requires Google Chrome at one of the known paths. Without Chrome
             the HTML is still written and its path reported so it can be
             printed manually.
@usage
    python3 scripts/utils/konsil_pdf.py analyses/2026-08-02/konsil
    python3 scripts/utils/konsil_pdf.py analyses/2026-08-02/konsil --einzeln

Exit Codes:
    0: PDF(s) erzeugt
    1: Verzeichnis fehlt oder enthaelt keine Markdown-Dateien
    2: Chrome nicht gefunden — HTML wurde geschrieben, PDF nicht
"""

import argparse
import html
import shutil
import subprocess
import sys
from pathlib import Path

CHROME_CANDIDATES = (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
)

CSS = """
@page { size: A4; margin: 20mm 18mm 18mm 18mm; }
* { box-sizing: border-box; }
body {
  font-family: -apple-system, "Helvetica Neue", Helvetica, Arial, sans-serif;
  font-size: 10.5pt; line-height: 1.55; color: #1a1a1a; margin: 0;
  -webkit-print-color-adjust: exact; print-color-adjust: exact;
}
h1 { font-size: 19pt; margin: 0 0 .3em; letter-spacing: -.01em;
     border-bottom: 2.5px solid #1a1a1a; padding-bottom: .28em; }
h2 { font-size: 13pt; margin: 1.5em 0 .45em; padding-top: .2em;
     border-top: 1px solid #d4d4d4; page-break-after: avoid; }
h3 { font-size: 11pt; margin: 1.1em 0 .35em; page-break-after: avoid; }
h1 + p em, h1 + p { margin-top: .4em; }
p, li { orphans: 3; widows: 3; }
ul, ol { padding-left: 1.35em; margin: .5em 0; }
li { margin: .22em 0; }
code { font-family: "SF Mono", Menlo, Consolas, monospace; font-size: .87em;
       background: #f2f2f2; padding: .1em .32em; border-radius: 3px; }
pre { background: #f7f7f7; border: 1px solid #e0e0e0; border-radius: 4px;
      padding: .7em .9em; overflow-x: auto; font-size: 9pt; line-height: 1.4;
      page-break-inside: avoid; }
pre code { background: none; padding: 0; }
blockquote { margin: .8em 0; padding: .5em .9em; border-left: 3px solid #999;
             background: #f7f7f7; font-size: .96em; }
table { border-collapse: collapse; width: 100%; margin: .8em 0; font-size: 9.5pt;
        page-break-inside: avoid; }
th, td { border: 1px solid #ccc; padding: .38em .55em; text-align: left;
         vertical-align: top; }
th { background: #efefef; font-weight: 600; }
hr { border: none; border-top: 1px solid #d0d0d0; margin: 1.4em 0; }
strong { font-weight: 600; }

.cover { page-break-after: always; padding-top: 45mm; }
.cover h1 { font-size: 27pt; border: none; padding: 0; margin-bottom: .15em; }
.cover .sub { font-size: 13pt; color: #555; margin-bottom: 2.5em; }
.cover .meta { font-size: 10pt; color: #444; line-height: 1.9; }
.cover .disclaimer { margin-top: 2.5em; padding: .9em 1.1em; background: #f5f5f5;
                     border-left: 3px solid #888; font-size: 9.5pt; color: #333; }
.toc { page-break-after: always; }
.toc ol { padding-left: 1.5em; }
.toc li { margin: .5em 0; font-size: 11pt; }
.doc { page-break-before: always; }
.doc:first-of-type { page-break-before: avoid; }
"""


def _md_to_html(text: str) -> str:
    import markdown
    return markdown.markdown(
        text,
        extensions=["tables", "fenced_code", "sane_lists", "attr_list", "nl2br"],
        output_format="html5",
    )


def _page(title: str, body: str) -> str:
    return (f"<!doctype html><html lang=de><head><meta charset=utf-8>"
            f"<title>{html.escape(title)}</title><style>{CSS}</style></head>"
            f"<body>{body}</body></html>")


def _find_chrome() -> "str | None":
    for c in CHROME_CANDIDATES:
        if Path(c).exists():
            return c
    return shutil.which("chromium") or shutil.which("google-chrome")


def _print_pdf(chrome: str, html_path: Path, pdf_path: Path) -> bool:
    cmd = [chrome, "--headless", "--disable-gpu", "--no-sandbox",
           "--no-pdf-header-footer", "--virtual-time-budget=8000",
           f"--print-to-pdf={pdf_path}", html_path.resolve().as_uri()]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if pdf_path.exists() and pdf_path.stat().st_size > 1000:
        return True
    print(f"  ! Chrome-Fehler fuer {pdf_path.name}: {r.stderr[-400:]}", file=sys.stderr)
    return False


def _title_of(md: str, fallback: str) -> str:
    for line in md.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def main() -> None:
    ap = argparse.ArgumentParser(description="Konsil-Gutachten als PDF rendern")
    ap.add_argument("verzeichnis", help="Ordner mit den Markdown-Gutachten")
    ap.add_argument("--einzeln", action="store_true",
                    help="Zusaetzlich ein PDF je Gutachten erzeugen")
    ap.add_argument("--titel", default="Interdisziplinäres Konsil",
                    help="Titel auf dem Deckblatt")
    args = ap.parse_args()

    src = Path(args.verzeichnis)
    if not src.is_dir():
        print(f"Kein Verzeichnis: {src}", file=sys.stderr)
        sys.exit(1)
    files = sorted(p for p in src.glob("*.md") if not p.name.startswith("_"))
    if not files:
        print(f"Keine Markdown-Dateien in {src}", file=sys.stderr)
        sys.exit(1)

    out = src / "pdf"
    out.mkdir(exist_ok=True)
    datum = src.parent.name

    docs = [(p, p.read_text(encoding="utf-8")) for p in files]
    titles = [_title_of(md, p.stem) for p, md in docs]

    cover = (
        f'<div class="cover"><h1>{html.escape(args.titel)}</h1>'
        f'<div class="sub">Musteranalyse aus lokalen Gesundheitsdaten</div>'
        f'<div class="meta">'
        f'<b>Stand:</b> {html.escape(datum)}<br>'
        f'<b>Umfang:</b> {len(docs)} Gutachten<br>'
        f'<b>Erstellung:</b> je Gutachten ein unabhängiger Durchlauf ohne Kenntnis '
        f'der übrigen Gutachten<br>'
        f'<b>Datenbasis:</b> Kyoro-HealthHub — Wearable-Zeitreihen, Laborwerte, '
        f'klinische Ereignisse, Anamnese</div>'
        f'<div class="disclaimer"><b>Keine ärztliche Diagnose.</b> Die folgenden Texte '
        f'sind automatisiert erstellte Musteranalysen aus Messdaten und Anamnese. '
        f'Sie ersetzen keine ärztliche Untersuchung, Beurteilung oder Behandlung und '
        f'sind als Gesprächsgrundlage gedacht. Medikamente dürfen auf dieser Grundlage '
        f'nicht eigenmächtig verändert oder abgesetzt werden.</div></div>'
    )
    toc = ('<div class="toc"><h1>Inhalt</h1><ol>'
           + "".join(f"<li>{html.escape(t)}</li>" for t in titles)
           + "</ol></div>")
    body = cover + toc + "".join(
        f'<div class="doc">{_md_to_html(md)}</div>' for _, md in docs)

    combined_html = out / "_konsil.html"
    combined_html.write_text(_page(args.titel, body), encoding="utf-8")

    chrome = _find_chrome()
    if not chrome:
        print("Chrome nicht gefunden — HTML geschrieben, kein PDF:", file=sys.stderr)
        print(f"  {combined_html}", file=sys.stderr)
        sys.exit(2)

    combined_pdf = out / f"Konsil_{datum}.pdf"
    ok = _print_pdf(chrome, combined_html, combined_pdf)
    if ok:
        kb = combined_pdf.stat().st_size // 1024
        print(f"✓ Sammelband: {combined_pdf}  ({kb} KB, {len(docs)} Gutachten)")

    if args.einzeln:
        for (p, md), title in zip(docs, titles):
            h = out / f"{p.stem}.html"
            h.write_text(_page(title, _md_to_html(md)), encoding="utf-8")
            pdf = out / f"{p.stem}.pdf"
            if _print_pdf(chrome, h, pdf):
                print(f"  ✓ {pdf.name}  ({pdf.stat().st_size // 1024} KB)")
            h.unlink(missing_ok=True)

    combined_html.unlink(missing_ok=True)
    sys.exit(0 if ok else 2)


if __name__ == "__main__":
    main()
