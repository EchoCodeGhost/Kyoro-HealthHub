# PPG-Kalibrierungsdatensätze Download (BIDMC, Pulse Transit Time PPG, PPG-BP, MIMIC-III-Ext-PPG)

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/calibration/download_ppg_datasets.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Lädt öffentliche PPG-Datensätze für die Presyncope-Detector-Kalibrierung (BACK-26, lokaler Feature-Backlog) herunter — Grundlage für Signalpipeline-, Atemfrequenz- und Qualitätsvalidierung, nicht synkopenspezifisch selbst.

## Relevanz

Ermöglicht den Download von Referenzdaten, essentiell für die Kalibrierung und Validierung

## Methode

BIDMC + Pulse Transit Time PPG: offene PhysioNet-WFDB-Datenbanken (Open Data Commons Attribution License, KEIN Credentialed-Zugang nötig), über die bereits im Projekt genutzte wfdb-Bibliothek (s. download_afdb.py). PPG-BP: offener Figshare-Datensatz (CC-BY), über die Figshare-API (dynamisch aufgelöste Download-URLs, keine hartcodierten Datei-Links). MIMIC-III-Ext-PPG: NUR mit eigenen PhysioNet-Credentialed-Zugangsdaten (Umgebungsvariablen, niemals im Code) — Credentialed Health Data License verbietet Weiterverteilung, daher standardmäßig übersprungen.

## Datenfluss

- **Liest:** `PhysioNet`, `(bidmc`, `pulse-transit-time-ppg`, `databases)`, `Figshare`, `API`, `(online)`
- **Schreibt:**

  ```
  data/calibration/bidmc/, data/calibration/pulse_transit_time_ppg/,
  data/calibration/ppgbp/, data/calibration/mimic_iii_ext_ppg/ (--credentialed only)
  ```

## Grenzen

Benötigt Internetverbindung + wfdb-Bibliothek + requests. PhysioNet- Datenbank-Slugs (`bidmc`, `pulse-transit-time-ppg`) können sich mit künftigen Versionen ändern — bei Fehlern zuerst die physionet.org- Projektseite auf einen neuen Slug/Versionspfad prüfen. MIMIC-III-Ext-PPG-Downloadpfad ist nach dem in PhysioNets eigener Doku dokumentierten wget-Muster inferiert, nicht selbst getestet (kein Zugriff auf physionet.org aus der Entwicklungsumgebung heraus).

## Referenzen

- Pimentel MAF, Johnson AEW, Charlton PH et al. (2017). Toward a Robust Estimation of Respiratory Rate From Pulse Oximeters. IEEE Transactions on Biomedical Engineering, 64(8):1914-1923. doi:10.1109/TBME.2016.2613124
- Liang Y, Chen Z, Liu G, Elgendi M (2018). A new, short-recorded photoplethysmogram dataset for blood pressure monitoring in China. Scientific Data, 5(1). doi:10.1038/sdata.2018.20
- Goldberger AL, Amaral LAN, Glass L, et al. 2000, Circulation,
- Goldberger AL, Amaral LAN, Glass L et al. (2000). PhysioBank, PhysioToolkit, and PhysioNet. Circulation, 101(23). doi:10.1161/01.CIR.101.23.e215

## Aufruf

```bash
python3 scripts/calibration/download_ppg_datasets.py                # open datasets only
python3 scripts/calibration/download_ppg_datasets.py --only bidmc
python3 scripts/calibration/download_ppg_datasets.py --only ptt-ppg
python3 scripts/calibration/download_ppg_datasets.py --only ppgbp
# Credentialed (needs an approved PhysioNet account for this specific project):
PHYSIONET_USER=<user> PHYSIONET_PASSWORD=<pw> \
    python3 scripts/calibration/download_ppg_datasets.py --credentialed
```
