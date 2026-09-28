# promote_anamnese_findings.py — Promotion logic for anamnese findings

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/utils/promote_anamnese_findings.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Implementiert die Promotion von Anamnese-Interview-Befunden in die bestehenden strukturierten JSON-Speicher (family_history.json, travel_history.json, exposure_history.json, known_risk_exposures.json). Unterstützt Track-zu-Ziel-Mapping, chronische vs. einmalige Expositionen, und menschliche Bestätigung pro Befund/Ziel.

## Relevanz

Ermöglicht die Förderung von Anamnese-Befunden, essentiell für die klinische Dokumentation

## Methode

1) Track-zu-Ziel-Mapping gemäß design.md Decision 3, 2) Chronische Expositionen identifizieren (Schlüsselwörter/Dauer), 3) Zielspezifische Einträge erstellen mit Pseudonym-Auflösung, 4) Nicht-interaktive Append-Funktionen aufrufen, 5) Bestätigung einholen, 6) Befund/Ziel-Paar in anamnese_promotions vermerken (Idempotenz).

## Datenfluss

- **Liest:** `health.db`, `(anamnese_findings`, `anamnese_sessions`, `anamnese_promotions)`
- **Schreibt:**

  ```
  health.db (anamnese_promotions);
  ~/.config/kyoro/{family,travel,exposure,known_risk_exposures}.json
  ```

## Grenzen

Keine automatische Promotion — menschliche Bestätigung pro Befund/Ziel erforderlich. Idempotenz-Tracking (Task 2.3): eine kleine Mapping-Tabelle (anamnese_promotions, Spalten finding_id/target_type/promoted_at, UNIQUE(finding_id, target_type)) statt einer Spalte auf anamnese_findings — ein Befund kann in mehrere Ziele promotet werden.

## Aufruf

```bash
python3 scripts/utils/promote_anamnese_findings.py 1
python3 scripts/utils/promote_anamnese_findings.py 1 --auto
python3 scripts/query/anamnese_interview.py --promote 1
```
