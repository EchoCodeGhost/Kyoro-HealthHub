# health_query.py — KI-gestützte Gesundheitsdaten-Analyse

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/query/health_query.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Interaktive Analyse-Schnittstelle für die Multi-Quellen-Gesundheitsdatenbank. Nutzt den konfigurierten LLM-Provider für natürlichsprachliche Evaluationen und SQL-Generierung. Ermöglicht medizinische Datenabfragen in natürlicher Sprache.

## Relevanz

Bietet umfassende Gesundheitsdatenabfragen, essentiell für die medizinische Analyse

## Methode

Nutzt den konfigurierten LLM-Provider (Mistral, Claude, etc.) für: 1. SQL-Generierung aus Natursprache (SYSTEM_SQL) 2. Interpretation von SQL-Ergebnissen (SYSTEM_INTERPRET) 3. Spezialisierte Analysen (HRV, Anomalien, Arrhythmie, Schlaf) Unterstützt interaktiven Modus, vorgefertigte Analysen (hrv, schlaf, etc.) und freie Fragen in natürlicher Sprache.

## Datenfluss

- **Liest:** `Alle`, `Tabellen`, `der`, `health.db`, `(siehe`, `SCHEMA-Konstante)`
- **Schreibt:** `STDERR/STDOUT (Analyseergebnisse), OUT_DIR/health_queries/ (Logs)`

## Grenzen

Keine medizinischen Diagnosen ohne Datenbeleg. SQL-Generierung begrenzt auf 50 Ergebnisse. Abfragen werden gegen das Schema validiert. Nicht für Echtzeit-Diagnostik geeignet. Ersetzt keine ärztliche Bewertung.

## Aufruf

```bash
python health_query.py                    # Interaktiver Modus
python health_query.py hrv               # HRV-Analyse
python health_query.py schlaf            # Schlafanalyse
python health_query.py "Wie war mein Sleep im März?" # Freie Frage
python health_query.py --sql "Wie war..." # Mit SQL-Output
python health_query.py healthcheck       # DB-Verbindungstest
```
