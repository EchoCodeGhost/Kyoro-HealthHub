# Polar Nightly Recharge — vollständige Analyse

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/sleep/analyse_nightly_recharge.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Analysiert Polar Nightly Recharge (ANS-Charge, Schlaf-Charge, Level 1–5) auf typisches Erholungsniveau, ANS-Status-Muster, Einschlafroutinen und Langzeittrend.

## Relevanz

Ermöglicht die Schlafanalyse, essentiell für die Schlafforschung und Gesundheitsüberwachung

## Methode

Verteilungsanalyse und Trendplot der Polar-Nightly-Recharge-Komponenten; eigene ANS-Status-Klassenlabels; Tiefschlaf/Effizienz/Kontinuität-Proxy als Schlafboost-Surrogate.

## Berechnung

```
ANS-Status (Polar proprietär, Klassen aus Herstellerdokumentation):
  ans_charge > +2.0  = Deutlicher Boost, > +0.5 = Leicht geladen,
  -0.5 bis +0.5 = Normal, < -0.5 = Leicht entladen, < -2.0 = Entladen
Schlaf-Boost-Proxy (heuristisch, projektintern):
  Tiefschlaf-Anteil: min(100, deep_pct / 25 × 100) — 25% als Top-Ziel
  Effizienz-Komponent: efficiency_pct
  Kontinuität-Komponent: min(100, continuity / 5 × 100)
Basis: ANS-Status auf Polar-Herstellerdaten; Proxy-Formel projektintern ohne externe Validierung.
```

## Datenfluss

- **Liest:** `polar_nightly_hrv`, `polar_sleep_hypnogram`, `session_metrics`
- **Schreibt:** `analyses/sleep/nightly_recharge_*.{md,png}`

## Grenzen

Heuristische Methode: Nightly Recharge ist ein proprietärer Polar-Algorithmus ohne veröffentlichte Validierungsstudie; ANS-Rate und Schlaf-Charge sind herstellerseitig nicht vollständig dokumentiert; Tiefschlaf-Normierung auf 25% ist konservativ gegenüber AASM-Norm (N3 13–23%); Proxy-Metriken für Schlafboost sind heuristisch.

## Referenzen

- Iber C, Ancoli-Israel S, Chesson AL, Quan SF (2007). The AASM Manual for the Scoring of Sleep and Associated Events: Rules, Terminology and Technical Specifications (1st ed.). American Academy of Sleep Medicine, Westchester, IL. (kein DOI verfügbar, Handbuch)
- Goldstone A, Baker FC, de Zambotti M (2018). Actigraphy in the digital health revolution: still asleep? Sleep, 41(9). doi:10.1093/sleep/zsy120

## Aufruf

```bash
python analyse_nightly_recharge.py
python analyse_nightly_recharge.py --help
python analyse_nightly_recharge.py --from 2024-01-01 --to 2024-12-31
```
