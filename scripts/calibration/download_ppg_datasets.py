#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""
PPG-Kalibrierungsdatensätze Download (BIDMC, Pulse Transit Time PPG, PPG-BP, MIMIC-III-Ext-PPG)

@tier        infrastructure
@purpose.de  Lädt öffentliche PPG-Datensätze für die Presyncope-Detector-Kalibrierung
             (BACK-26, lokaler Feature-Backlog) herunter — Grundlage für Signalpipeline-,
             Atemfrequenz- und Qualitätsvalidierung, nicht synkopenspezifisch selbst.
@purpose.en  Downloads public PPG datasets for presyncope-detector calibration
             (BACK-26, local feature backlog) — basis for signal pipeline, respiratory
             rate, and quality validation, not syncope-specific data itself.
@method.de   BIDMC + Pulse Transit Time PPG: offene PhysioNet-WFDB-Datenbanken
             (Open Data Commons Attribution License, KEIN Credentialed-Zugang nötig),
             über die bereits im Projekt genutzte wfdb-Bibliothek (s. download_afdb.py).
             PPG-BP: offener Figshare-Datensatz (CC-BY), über die Figshare-API
             (dynamisch aufgelöste Download-URLs, keine hartcodierten Datei-Links).
             MIMIC-III-Ext-PPG: NUR mit eigenen PhysioNet-Credentialed-Zugangsdaten
             (Umgebungsvariablen, niemals im Code) — Credentialed Health Data License
             verbietet Weiterverteilung, daher standardmäßig übersprungen.
@method.en   BIDMC + Pulse Transit Time PPG: open PhysioNet WFDB databases (Open Data
             Commons Attribution License, NO credentialed access needed), via the
             wfdb library already used elsewhere in this project (see download_afdb.py).
             PPG-BP: open Figshare dataset (CC-BY), via the Figshare API (dynamically
             resolved download URLs, no hardcoded file links).
             MIMIC-III-Ext-PPG: ONLY with the user's own PhysioNet credentialed
             credentials (environment variables, never in code) — its Credentialed
             Health Data License forbids redistribution, so skipped by default.
@reads       PhysioNet (bidmc, pulse-transit-time-ppg databases), Figshare API (online)
@writes      data/calibration/bidmc/, data/calibration/pulse_transit_time_ppg/,
             data/calibration/ppgbp/, data/calibration/mimic_iii_ext_ppg/ (--credentialed only)
@refs        Pimentel MAF, Johnson AEW, Charlton PH et al. (2017). Toward a Robust Estimation of Respiratory Rate From Pulse Oximeters. IEEE Transactions on Biomedical Engineering, 64(8):1914-1923. doi:10.1109/TBME.2016.2613124
             Liang Y, Chen Z, Liu G, Elgendi M (2018). A new, short-recorded photoplethysmogram dataset for blood pressure monitoring in China. Scientific Data, 5(1). doi:10.1038/sdata.2018.20
             Goldberger AL, Amaral LAN, Glass L, et al. 2000, Circulation,
             Goldberger AL, Amaral LAN, Glass L et al. (2000). PhysioBank, PhysioToolkit, and PhysioNet. Circulation, 101(23). doi:10.1161/01.CIR.101.23.e215

@relevance.de  Ermöglicht den Download von Referenzdaten, essentiell für die Kalibrierung und Validierung
@relevance.en  Enables download of reference data, essential for calibration and validation
@limits.de   Benötigt Internetverbindung + wfdb-Bibliothek + requests. PhysioNet-
             Datenbank-Slugs (`bidmc`, `pulse-transit-time-ppg`) können sich mit
             künftigen Versionen ändern — bei Fehlern zuerst die physionet.org-
             Projektseite auf einen neuen Slug/Versionspfad prüfen.
             MIMIC-III-Ext-PPG-Downloadpfad ist nach dem in PhysioNets eigener
             Doku dokumentierten wget-Muster inferiert, nicht selbst getestet
             (kein Zugriff auf physionet.org aus der Entwicklungsumgebung heraus).
@limits.en   Requires internet connection + wfdb library + requests. PhysioNet
             database slugs (`bidmc`, `pulse-transit-time-ppg`) may change with
             future versions — check the physionet.org project page for a new
             slug/version path if downloads fail.
             The MIMIC-III-Ext-PPG download path is inferred from PhysioNet's own
             documented wget pattern, not independently tested (no access to
             physionet.org from the development environment this was written in).
@usage
    python3 scripts/calibration/download_ppg_datasets.py                # open datasets only
    python3 scripts/calibration/download_ppg_datasets.py --only bidmc
    python3 scripts/calibration/download_ppg_datasets.py --only ptt-ppg
    python3 scripts/calibration/download_ppg_datasets.py --only ppgbp
    # Credentialed (needs an approved PhysioNet account for this specific project):
    PHYSIONET_USER=<user> PHYSIONET_PASSWORD=<pw> \\
        python3 scripts/calibration/download_ppg_datasets.py --credentialed
"""
import argparse
import os
import sys
from pathlib import Path

CALIBRATION_DIR = Path(__file__).parent.parent.parent / "data" / "calibration"

# PhysioNet project slugs — verify against physionet.org/content/<slug>/ if a
# download fails; PhysioNet occasionally reorganizes URLs between versions.
BIDMC_DB_SLUG = "bidmc"
PTT_PPG_DB_SLUG = "pulse-transit-time-ppg"

# Figshare article ID for the PPG-BP Database (Liang et al. 2018),
# doi:10.6084/m9.figshare.5459299 — resolved dynamically via the Figshare API
# below rather than hardcoding a specific file URL, since those can change
# between dataset versions.
PPGBP_FIGSHARE_ARTICLE_ID = 5459299

# MIMIC-III-Ext-PPG: credentialed PhysioNet project — only the slug is public
# knowledge, the data itself requires an approved PhysioNet account for this
# specific project. Verify the exact slug/version on physionet.org before use;
# this is a placeholder pending confirmation, since Credentialed Health Data
# License datasets can't be test-accessed from an unauthenticated environment.
MIMIC_III_EXT_PPG_SLUG = "mimic-iii-ext-ppg"


def download_wfdb_database(slug: str, outdir: Path, label: str) -> None:
    """Downloads an open (non-credentialed) PhysioNet WFDB database — same
    approach as download_afdb.py, reused here for BIDMC / Pulse Transit Time PPG."""
    import wfdb

    outdir.mkdir(parents=True, exist_ok=True)
    print(f"\n=== {label} ({slug}) → {outdir} ===")
    try:
        records = wfdb.get_record_list(slug)
    except Exception as e:
        print(f"  FEHLER beim Abrufen der Record-Liste: {e}", file=sys.stderr)
        print(f"  Prüfe https://physionet.org/content/{slug}/ auf einen aktuellen Slug/Versionspfad.")
        return

    print(f"  {len(records)} Records gefunden")
    for i, rec in enumerate(records, 1):
        target = outdir / f"{rec}.hea"
        if target.exists():
            print(f"  [{i:>3}/{len(records)}] {rec} ... bereits vorhanden, übersprungen")
            continue
        print(f"  [{i:>3}/{len(records)}] {rec} ...", end="", flush=True)
        try:
            wfdb.dl_database(slug, dl_dir=str(outdir), records=[rec])
            print(" OK")
        except Exception as e:
            print(f" FEHLER: {e}", file=sys.stderr)

    print(f"  Fertig. {len(list(outdir.glob('*.hea')))} .hea-Dateien in {outdir}")


def download_ppgbp(outdir: Path) -> None:
    """Downloads the open (CC-BY) PPG-BP Database via the Figshare API —
    resolves the actual file download URL(s) dynamically rather than
    hardcoding a versioned link."""
    import requests

    outdir.mkdir(parents=True, exist_ok=True)
    print(f"\n=== PPG-BP Database (Figshare {PPGBP_FIGSHARE_ARTICLE_ID}) → {outdir} ===")

    api_url = f"https://api.figshare.com/v2/articles/{PPGBP_FIGSHARE_ARTICLE_ID}"
    try:
        resp = requests.get(api_url, timeout=30)
        resp.raise_for_status()
        article = resp.json()
    except Exception as e:
        print(f"  FEHLER beim Abrufen der Figshare-Metadaten: {e}", file=sys.stderr)
        print(f"  Prüfe https://figshare.com/articles/dataset/PPG-BP_Database_zip/{PPGBP_FIGSHARE_ARTICLE_ID} manuell.")
        return

    files = article.get("files", [])
    if not files:
        print("  Keine Dateien in den Figshare-Metadaten gefunden.", file=sys.stderr)
        return

    for f in files:
        name = f["name"]
        url = f["download_url"]
        target = outdir / name
        if target.exists():
            print(f"  {name} ... bereits vorhanden, übersprungen")
            continue
        print(f"  {name} ...", end="", flush=True)
        try:
            with requests.get(url, stream=True, timeout=120) as r:
                r.raise_for_status()
                with open(target, "wb") as fh:
                    for chunk in r.iter_content(chunk_size=1 << 20):
                        fh.write(chunk)
            print(" OK")
        except Exception as e:
            print(f" FEHLER: {e}", file=sys.stderr)

    print(f"  Fertig. {len(list(outdir.iterdir()))} Dateien in {outdir}")
    print("  Zitation nicht vergessen: Liang et al. 2018, doi:10.1038/sdata.2018.20")


def download_mimic_iii_ext_ppg(outdir: Path) -> None:
    """Credentialed PhysioNet dataset — requires PHYSIONET_USER/PHYSIONET_PASSWORD
    env vars for an account with approved access to this specific project.
    NEVER hardcode credentials here or commit downloaded files — the
    Credentialed Health Data License forbids redistribution (see BACK-26
    licensing discussion in the local feature backlog)."""
    import requests

    user = os.environ.get("PHYSIONET_USER")
    password = os.environ.get("PHYSIONET_PASSWORD")
    if not user or not password:
        print(
            "\n=== MIMIC-III-Ext-PPG übersprungen ===\n"
            "  Setze PHYSIONET_USER und PHYSIONET_PASSWORD (eigener, für dieses\n"
            "  Projekt freigeschalteter PhysioNet-Account) und rufe erneut mit\n"
            "  --credentialed auf.",
            file=sys.stderr,
        )
        return

    outdir.mkdir(parents=True, exist_ok=True)
    print(f"\n=== MIMIC-III-Ext-PPG ({MIMIC_III_EXT_PPG_SLUG}) → {outdir} ===")
    print("  ACHTUNG: Rohdaten hier NIEMALS committen — Credentialed Health Data License")
    print("  verbietet Weiterverteilung (s. lokaler Feature-Backlog BACK-26).")

    index_url = f"https://physionet.org/files/{MIMIC_III_EXT_PPG_SLUG}/"
    try:
        resp = requests.get(index_url, auth=(user, password), timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"  FEHLER beim Zugriff: {e}", file=sys.stderr)
        print(f"  Prüfe https://physionet.org/content/{MIMIC_III_EXT_PPG_SLUG}/ auf den")
        print("  korrekten Slug/Versionspfad und ob der Account für dieses Projekt")
        print("  freigeschaltet ist.")
        return

    print("  Zugriff erfolgreich, aber automatisches Dateilisting ist hier nicht")
    print("  implementiert (kein authentifizierter Test aus der Entwicklungsumgebung")
    print(f"  möglich) — bitte manuell fortsetzen, z. B.:")
    print(f"    wget -r -N -c -np --user {user} --ask-password {index_url}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Lädt öffentliche PPG-Kalibrierungsdatensätze für BACK-26 herunter."
    )
    parser.add_argument(
        "--only", choices=["bidmc", "ptt-ppg", "ppgbp"], default=None,
        help="Nur diesen einzelnen offenen Datensatz laden (Default: alle drei offenen)",
    )
    parser.add_argument(
        "--credentialed", action="store_true",
        help="Zusätzlich MIMIC-III-Ext-PPG versuchen (braucht PHYSIONET_USER/PHYSIONET_PASSWORD)",
    )
    args = parser.parse_args()

    targets = [args.only] if args.only else ["bidmc", "ptt-ppg", "ppgbp"]

    if "bidmc" in targets:
        download_wfdb_database(BIDMC_DB_SLUG, CALIBRATION_DIR / "bidmc", "BIDMC PPG and Respiration Dataset")
    if "ptt-ppg" in targets:
        download_wfdb_database(PTT_PPG_DB_SLUG, CALIBRATION_DIR / "pulse_transit_time_ppg", "Pulse Transit Time PPG Dataset")
    if "ppgbp" in targets:
        download_ppgbp(CALIBRATION_DIR / "ppgbp")

    if args.credentialed:
        download_mimic_iii_ext_ppg(CALIBRATION_DIR / "mimic_iii_ext_ppg")


if __name__ == "__main__":
    main()
