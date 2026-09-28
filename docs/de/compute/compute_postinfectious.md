# Reaktionsmuster-Erkennung — Heuristische Identifizierung via rollierender persönlicher Baseline.

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/compute/compute_postinfectious.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Erkennt Reaktionsmuster nach Belastung, indem Belastung an Tag N mit HRV/RHR-Abweichungen an Tag N+1 relativ zu einer individuellen rollenden Baseline verglichen wird.

## Relevanz

Ermöglicht die Analyse postinfektiöser Muster, essentiell für die Langzeitüberwachung

## Methode

Rollende 28-Tage-Baseline bestimmt personenspezifische Schwellenwerte für HRV (Root Mean Square of Successive Differences) und RHR (Ruheherzfrequenz). Tag N+1, N+2 und N+3 nach Belastung werden geprüft; ein Reaktionsmuster-Signal entsteht, wenn HRV an einem dieser Tage mehr als 1 Standardabweichung unter der Baseline liegt ODER RHR mehr als 1 Standardabweichung über der Baseline liegt (die stärkste Abweichung der drei Tage wird berichtet). Belastung wird aus Schritten, aktivem Energieverbrauch und Stress-Score berechnet.

## Berechnung

```
direct = HRV_Abweichung * 40 + RHR_Abweichung * 30 + Belastungsintensitaet * 30
```

## Datenfluss

- **Liest:** `measurements`, `polar_nightly_hrv`, `daily_stress`, `sessions`
- **Schreibt:** `pem_correlation`

## Grenzen

Heuristische Methode: ±1-SD-Schwelle ist eine statistische Heuristik, keine klinisch validierte Definition. 28-Tage-Baseline ist bei stark schwankenden Daten instabil und benötigt mindestens 20 Tage mit gültigen Daten. Reaktionsmuster-Signale basieren auf individuellen Mustern und sind nicht verallgemeinerbar. Ersetzt keine medizinische Diagnose.

## Referenzen

- Carruthers BM, van de Sande MI, De Meirleir KL et al. (2011). Myalgic encephalomyelitis: International Consensus Criteria. Journal of Internal Medicine, 270(4):327-338. doi:10.1111/j.1365-2796.2011.02428.x
- [UNVERIFIZIERT] "Jason et al. 2021, Frontiers in Medicine, doi:10.3389/fmed.2021.637976" — DOI löst nicht auf, kein Jason-Paper 2021 in diesem Journal-Jahrgang auffindbar (Crossref-Journal-Direktsuche negativ). Vor Verwendung/Vertrauen manuell prüfen.

## Aufruf

```bash
python compute_postinfectious.py
python compute_postinfectious.py --update
python compute_postinfectious.py --from 2024-01-01 --to 2024-12-31
python compute_postinfectious.py --person self
```
