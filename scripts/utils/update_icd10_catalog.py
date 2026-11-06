#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
update_icd10_catalog.py — ICD-10-GM-Katalog lokal installieren/aktualisieren

@tier        infrastructure
@purpose.de  Installiert oder aktualisiert den lokalen ICD-10-GM-Katalog
             (data/reference/icd10gm/), den scripts/modules/icd10_catalog.py
             zum Validieren von ICD-Codes und zum Code↔Text-Plausibilitäts-
             Check nutzt. Der Katalog wird NICHT im Repo gebündelt (siehe
             Moduldocstring von icd10_catalog.py @limits) -- jede
             Installation muss diesen Downloadschritt selbst einmal
             durchlaufen.
@purpose.en  Installs or updates the local ICD-10-GM catalog
             (data/reference/icd10gm/) that scripts/modules/icd10_catalog.py
             uses for ICD code validation and the code↔text plausibility
             check. The catalog is NOT bundled in the repo (see
             icd10_catalog.py's module docstring @limits) -- every
             installation must run this download step itself once.
@method.de   Drei Modi: --check fragt nur die BfArM-Downloadseite ab und
             vergleicht die dort gefundene neueste Jahresversion mit der
             lokal installierten (aus dem Dateinamen in data/reference/
             icd10gm/), OHNE etwas herunterzuladen oder Bedingungen zu
             akzeptieren. --download führt den tatsächlichen Download durch:
             BfArM verlangt PRO NUTZER*IN die explizite Zustimmung zu einem
             Nutzungsvertrag (Downloadbedingungen) -- dieses Skript zeigt
             daher vor jedem Download eine Kurzfassung der Bedingungen und
             verlangt eine explizite Bestätigung (interaktiv per Eingabe
             oder via --accept-terms für nicht-interaktive Läufe), NIE eine
             automatische/stellvertretende Zustimmung. Die aktuelle
             Download-URL wird NICHT für ein festes Jahr hartkodiert,
             sondern bei jedem Lauf frisch aus der BfArM-Downloadseite
             herausgelesen (Regex auf "icd10gmJJJJsyst-meta_zip.html") --
             damit funktioniert --download auch nächstes Jahr ohne
             Codeänderung, solange BfArM das URL-Schema beibehält.
             --from-zip <pfad> überspringt den Download komplett: für
             Nutzer*innen, die die ZIP bereits manuell im Browser
             heruntergeladen (und die Bedingungen dort akzeptiert) haben.
             In allen Fällen wird aus der ZIP nur
             Klassifikationsdateien/icd10gmJJJJsyst_kodes.txt entpackt (die
             Code+Titel-Liste, siehe icd10_catalog.py) -- der Rest (Mortalitäts-
             listen, PDFs, Alphabet-Verzeichnis) wird verworfen, um
             data/reference/icd10gm/ klein zu halten; dieselbe Datei wird
             UNVERÄNDERT übernommen (kein Textumbau -- siehe
             Urheberrechts-Änderungsverbot, § 62 UrhG, in den BfArM-
             Downloadbedingungen).
@method.en   Three modes: --check only queries the BfArM downloads page and
             compares the newest year found there against the locally
             installed one (from the filename in data/reference/icd10gm/),
             WITHOUT downloading anything or accepting any terms.
             --download performs the actual download: BfArM requires EACH
             USER to explicitly accept a usage contract (download
             conditions) -- this script therefore shows a short summary of
             the terms before every download and requires explicit
             confirmation (interactively, or via --accept-terms for
             non-interactive runs), NEVER an automatic/on-behalf-of
             acceptance. The current download URL is NOT hardcoded to one
             year -- it's read fresh from the BfArM downloads page on every
             run (regex for "icd10gmYYYYsyst-meta_zip.html"), so --download
             keeps working next year without a code change, as long as
             BfArM keeps the URL scheme. --from-zip <path> skips the
             download entirely: for users who already downloaded the ZIP
             manually in their browser (and accepted the terms there). In
             every case, only Klassifikationsdateien/icd10gmYYYYsyst_kodes.txt
             is extracted from the ZIP (the code+title list, see
             icd10_catalog.py) -- everything else (mortality lists, PDFs,
             the alphabetical index) is discarded to keep data/reference/
             icd10gm/ small; that one file is kept UNCHANGED (no text
             rewriting -- see the no-alteration clause, § 62 UrhG, in
             BfArM's download conditions).
@reads       https://www.bfarm.de/.../Kodiersysteme/Services/Downloads/
             (online, nur --check und --download)
@writes      data/reference/icd10gm/icd10gmJJJJsyst_kodes.txt (unveränderte
             Kopie aus der BfArM-ZIP); data/reference/icd10gm/NOTICE.txt
             (Pflicht-Quellenangabe nach § 63 UrhG, siehe
             Downloadbedingungen-Anhang)
@limits.de   Das BfArM-Seitenlayout/URL-Schema kann sich ändern -- schlägt
             dann mit einer klaren Fehlermeldung fehl (kein Codeänderungs-
             bedarf garantiert). Prüft NICHT automatisch auf ICD-11 -- die
             BfArM-Downloadseite bietet aktuell nur ICD-10-GM/OPS/ICD-10-WHO/
             Alpha-ID-SE/ICD-O-3/ICF an; --check gibt dazu nur einen
             statischen Hinweis aus, kein Live-Signal, ob/wann Deutschland
             auf ICD-11 zur Abrechnung umstellt (das ist Stand dieses
             Projekts keine automatisch beobachtbare Tatsache).
@limits.en   BfArM's page layout/URL scheme can change -- this then fails
             with a clear error message (no guarantee against needing a
             code update). Does NOT auto-check for ICD-11 -- the BfArM
             downloads page currently only offers ICD-10-GM/OPS/ICD-10-WHO/
             Alpha-ID-SE/ICD-O-3/ICF; --check only prints a static note
             about this, not a live signal of whether/when Germany switches
             to ICD-11 for billing (as of this project, not an automatically
             observable fact).

@relevance.de  Hält den lokalen ICD-10-GM-Katalog aktuell, essentiell dafür, dass der Code↔Text-Plausibilitätscheck nicht gegen eine veraltete Jahresversion prüft
@relevance.en  Keeps the local ICD-10-GM catalog current, essential so the code↔text plausibility check doesn't validate against a stale year's version
@usage
    python3 update_icd10_catalog.py --check
    python3 update_icd10_catalog.py --download --accept-terms
    python3 update_icd10_catalog.py --from-zip ~/Downloads/icd10gm2026syst-meta.zip
"""

from __future__ import annotations

import argparse
import re
import sys
import urllib.request
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from modules.i18n import t, add_lang_arg, apply_lang_from_args  # noqa: E402

REPO_ROOT = Path(__file__).parents[2]
CATALOG_DIR = REPO_ROOT / "data" / "reference" / "icd10gm"
DOWNLOADS_PAGE = "https://www.bfarm.de/DE/Kodiersysteme/Services/Downloads/_node.html"
CONFIRM_FORM_ACTION = "https://www.bfarm.de/SiteGlobals/Forms/Downloadbestaetigung/Downloadbestaetigung_Formular.html"
USER_AGENT = "Kyoro-HealthHub/update_icd10_catalog.py (lokales Health-Datenprojekt, siehe github.com/EchoCodeGhost/Kyoro-HealthHub)"

TERMS_SUMMARY_DE = (
    "BfArM verlangt vor jedem Download Zustimmung zu einem Nutzungsvertrag:\n"
    "  - Die ICD-10-GM-Systematik ist ein amtliches Werk (§ 5 Abs. 2 UrhG).\n"
    "  - Vervielfältigung/Verbreitung ist erlaubt, SOLANGE:\n"
    "    * keine inhaltliche Änderung (§ 62 UrhG) -- dieses Skript kopiert\n"
    "      die Kodes-Datei unverändert, siehe NOTICE.txt nach dem Download.\n"
    "    * Quellenangabe beigefügt wird (§ 63 UrhG) -- wird automatisch als\n"
    "      NOTICE.txt neben die Daten geschrieben.\n"
    "    * keine kommerzielle Werbung enthalten ist.\n"
    "  - Volltext: https://www.bfarm.de/SharedDocs/Downloads/DE/Kodiersysteme/"
    "downloadbedingungen_20250801.pdf\n"
    "Dieser Download-Schritt schließt EINEN eigenen Nutzungsvertrag mit dem\n"
    "BfArM für DICH ab -- nicht stellvertretend für andere Nutzer*innen."
)
TERMS_SUMMARY_EN = (
    "BfArM requires accepting a usage contract before every download:\n"
    "  - The ICD-10-GM classification is an official work (§ 5(2) German\n"
    "    copyright law).\n"
    "  - Reproduction/distribution is permitted AS LONG AS:\n"
    "    * no content alteration (§ 62) -- this script copies the codes\n"
    "      file unchanged, see NOTICE.txt after download.\n"
    "    * a source citation is included (§ 63) -- written automatically\n"
    "      as NOTICE.txt next to the data.\n"
    "    * no commercial advertising is included.\n"
    "  - Full text: https://www.bfarm.de/SharedDocs/Downloads/DE/Kodiersysteme/"
    "downloadbedingungen_20250801.pdf\n"
    "This download step enters YOUR OWN usage contract with BfArM -- not on\n"
    "behalf of any other user."
)

NOTICE_TEXT = (
    "Quellenangabe (nach § 63 UrhG, siehe BfArM-Downloadbedingungen):\n\n"
    "Die vorliegende Ausgabe beruht auf der vollständigen amtlichen Fassung der\n"
    "Internationalen statistischen Klassifikation der Krankheiten und verwandter\n"
    "Gesundheitsprobleme, 10. Revision (ICD-10-GM), herausgegeben vom\n"
    "Bundesinstitut für Arzneimittel und Medizinprodukte (BfArM) im Auftrag des\n"
    "Bundesministeriums für Gesundheit (BMG).\n"
    "© Weltgesundheitsorganisation (WHO) 1992 / Commonwealth of Australia 1998\n"
    "(Übersetzungsrechte an das BfArM vergeben).\n\n"
    "Diese Datei (icd10gm*syst_kodes.txt) wurde unverändert aus der offiziellen\n"
    "BfArM-ZIP-Distribution übernommen (kein Textumbau, § 62 UrhG\n"
    "Änderungsverbot). Nicht im Kyoro-HealthHub-Repository enthalten --\n"
    "installiert über scripts/utils/update_icd10_catalog.py, jede Installation\n"
    "hat ihren eigenen Download-Vorgang/Nutzungsvertrag mit dem BfArM.\n"
)


def _fetch(url: str, data: bytes | None = None) -> bytes:
    req = urllib.request.Request(url, data=data, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def _find_meta_zip_url(listing_html: str) -> tuple[str, str] | None:
    """(url, jahr) der aktuellsten 'syst-meta_zip.html'-URL in der
    BfArM-Downloadseite, oder None. Kein hartkodiertes Jahr -- siehe
    Moduldocstring @method."""
    matches = re.findall(
        r'href="(https://www\.bfarm\.de/SharedDocs/Downloads/DE/Kodiersysteme/'
        r'klassifikationen/icd-10-gm/version(\d{4})/icd10gm\d{4}syst-meta_zip\.html[^"]*)"',
        listing_html,
    )
    if not matches:
        return None
    url, year = max(matches, key=lambda m: m[1])
    return url.replace("&amp;", "&"), year


def cmd_check(lang: str) -> None:
    html = _fetch(DOWNLOADS_PAGE).decode("utf-8", errors="replace")
    found = _find_meta_zip_url(html)
    if not found:
        print(t(
            "Konnte die aktuelle ICD-10-GM-Version auf der BfArM-Seite nicht finden "
            "(Seitenlayout geändert?). Bitte manuell prüfen: " + DOWNLOADS_PAGE,
            "Could not find the current ICD-10-GM version on the BfArM page "
            "(page layout changed?). Please check manually: " + DOWNLOADS_PAGE,
        ))
        sys.exit(1)
    _, remote_year = found
    local_year = _installed_year()
    if local_year is None:
        print(t(
            f"Kein lokaler ICD-10-GM-Katalog installiert. Aktuelle BfArM-Version: {remote_year}.\n"
            f"Installieren mit: python3 update_icd10_catalog.py --download --accept-terms",
            f"No local ICD-10-GM catalog installed. Current BfArM version: {remote_year}.\n"
            f"Install with: python3 update_icd10_catalog.py --download --accept-terms",
        ))
    elif local_year < remote_year:
        print(t(
            f"Update verfügbar: installiert={local_year}, aktuell bei BfArM={remote_year}.\n"
            f"Aktualisieren mit: python3 update_icd10_catalog.py --download --accept-terms",
            f"Update available: installed={local_year}, current at BfArM={remote_year}.\n"
            f"Update with: python3 update_icd10_catalog.py --download --accept-terms",
        ))
    else:
        print(t(f"Aktuell. Installiert: {local_year}.", f"Up to date. Installed: {local_year}."))
    print(t(
        "\nHinweis: Dieser Check prüft nur auf eine neuere ICD-10-GM-Jahresversion. "
        "Deutschland rechnet aktuell ausschließlich mit ICD-10-GM ab, kein "
        "automatisches ICD-11-Signal (Stand: Zeitpunkt dieses Checks) -- bei Zweifel "
        "manuell prüfen: https://www.bfarm.de/DE/Kodiersysteme/Klassifikationen/ICD/_node.html",
        "\nNote: this check only looks for a newer ICD-10-GM year. Germany currently "
        "bills exclusively under ICD-10-GM, no automatic ICD-11 signal (as of this "
        "check) -- if in doubt, check manually: "
        "https://www.bfarm.de/DE/Kodiersysteme/Klassifikationen/ICD/_node.html",
    ))


def _installed_year() -> str | None:
    if not CATALOG_DIR.exists():
        return None
    candidates = sorted(CATALOG_DIR.glob("icd10gm*syst_kodes.txt"))
    if not candidates:
        return None
    m = re.search(r"icd10gm(\d{4})syst_kodes\.txt$", candidates[-1].name)
    return m.group(1) if m else None


def _install_from_zip_bytes(zip_bytes: bytes, lang: str) -> None:
    CATALOG_DIR.mkdir(parents=True, exist_ok=True)
    import io
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        kodes_names = [n for n in zf.namelist() if re.search(r"icd10gm\d{4}syst_kodes\.txt$", n)]
        if not kodes_names:
            print(t("Kodes-Datei nicht in der ZIP gefunden -- falsche Datei?",
                    "Codes file not found in the ZIP -- wrong file?"))
            sys.exit(1)
        name = kodes_names[0]
        target = CATALOG_DIR / Path(name).name
        with zf.open(name) as src, target.open("wb") as dst:
            dst.write(src.read())
    (CATALOG_DIR / "NOTICE.txt").write_text(NOTICE_TEXT, encoding="utf-8")
    print(t(f"Installiert: {target}", f"Installed: {target}"))


def cmd_download(accept_terms: bool, lang: str) -> None:
    print(TERMS_SUMMARY_DE if lang == "de" else TERMS_SUMMARY_EN)
    if not accept_terms:
        answer = input(t(
            "\nStimmst du den Downloadbedingungen für DIESEN Download zu? [ja/nein]: ",
            "\nDo you accept the download conditions for THIS download? [yes/no]: ",
        )).strip().lower()
        if answer not in ("ja", "j", "yes", "y"):
            print(t("Abgebrochen, keine Zustimmung erteilt.", "Aborted, no consent given."))
            sys.exit(1)

    html = _fetch(DOWNLOADS_PAGE).decode("utf-8", errors="replace")
    found = _find_meta_zip_url(html)
    if not found:
        print(t("Konnte die Download-URL nicht finden (Seitenlayout geändert?).",
                "Could not find the download URL (page layout changed?)."))
        sys.exit(1)
    confirm_url, year = found

    confirm_html = _fetch(confirm_url).decode("utf-8", errors="replace")
    form_match = re.search(r'<form name="downloadConfirm".*?</form>', confirm_html, re.S)
    if not form_match:
        print(t("Bestätigungsformular nicht gefunden (Seitenlayout geändert?).",
                "Confirmation form not found (page layout changed?)."))
        sys.exit(1)
    form_html = form_match.group(0)

    def _field(name: str) -> str:
        m = re.search(rf'name="{re.escape(name)}"\s+value="([^"]*)"', form_html)
        return m.group(1) if m else ""

    import urllib.parse
    payload = urllib.parse.urlencode({
        "nn": _field("nn"),
        "resourceId": _field("resourceId"),
        "input_": _field("input_"),
        "pageLocale": _field("pageLocale") or "de",
        "datenschutzhinweis": "accept",
        "datenschutzhinweis.GROUP": "1",
        "publicationID": _field("publicationID"),
        "submit": "Jetzt herunterladen",
        "calledDcoumentID": "",
    }).encode("utf-8")

    print(t(f"Lade ICD-10-GM {year} herunter...", f"Downloading ICD-10-GM {year}..."))
    zip_bytes = _fetch(CONFIRM_FORM_ACTION, data=payload)
    _install_from_zip_bytes(zip_bytes, lang)


def cmd_from_zip(path: Path, lang: str) -> None:
    if not path.exists():
        print(t(f"Nicht gefunden: {path}", f"Not found: {path}"))
        sys.exit(1)
    _install_from_zip_bytes(path.read_bytes(), lang)


def main() -> None:
    parser = argparse.ArgumentParser(description=t(
        "ICD-10-GM-Katalog lokal installieren/aktualisieren/prüfen",
        "Install/update/check the local ICD-10-GM catalog",
    ))
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true",
                        help=t("Nur prüfen, ob eine neuere Version bei BfArM verfügbar ist",
                               "Only check whether a newer version is available at BfArM"))
    group.add_argument("--download", action="store_true",
                        help=t("Aktuelle Version bei BfArM herunterladen (Zustimmung erforderlich)",
                               "Download the current version from BfArM (consent required)"))
    group.add_argument("--from-zip", type=Path, default=None,
                        help=t("Bereits manuell heruntergeladene ZIP-Datei verwenden",
                               "Use an already manually downloaded ZIP file"))
    parser.add_argument("--accept-terms", action="store_true",
                        help=t("Downloadbedingungen nicht-interaktiv akzeptieren (nur mit --download)",
                               "Accept download conditions non-interactively (only with --download)"))
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)
    lang = getattr(args, "lang", "de") or "de"

    if args.check:
        cmd_check(lang)
    elif args.download:
        cmd_download(args.accept_terms, lang)
    elif args.from_zip:
        cmd_from_zip(args.from_zip, lang)


if __name__ == "__main__":
    main()
