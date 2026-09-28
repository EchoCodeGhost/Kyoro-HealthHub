# analyse_saliva_ph.py — Speichel-pH Heimmonitoring Trendanalyse

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/manual/analyse_saliva_ph.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Analysiert Speichel-pH-Daten aus Heimmonitoring

## Relevanz

Ermöglicht die Gesundheitsdatenanalyse, essentiell für die medizinische Diagnostik

## Methode

Liest Speichel-pH-Daten aus medicine.db (lab_manual, parameter="Speichel-pH"), gruppiert nach Kontext (fasting_morning, post_meal_1h …) und erstellt: - Trendtabelle aller Kontexte über Zeit - Alarm-Flagging anhand der Schwellen in ~/.config/kyoro/saliva_ph_ranges.json - Kontext-Mittelwerte + Min/Max-Spanne - Optional: LLM-Kommentar (Internist/Allergologe-Perspektive) - Optional: Plot (pH-Verlauf pro Kontext)

## Berechnung

```
Anomalie-Score basierend auf Anteil der Messungen außerhalb kontextspezifischer pH-Referenzbereiche
```

## Datenfluss

- **Liest:** `medicine.db`, `(lab_manual)`, `~/.config/kyoro/saliva_ph_ranges.json`
- **Schreibt:** `Analyseergebnisse als Markdown (analyses/manual/)`

## Grenzen

Heuristische Methode. pH-Streifen-Genauigkeit ±0,5; pH-Meter-Werte präziser. Kontext-Trennung hängt von korrekter CSV-Eingabe ab.

## Referenzen

- Tenovuo J, Lagerlöf F (1994). Saliva. In: Thylstrup A, Fejerskov O (Hrsg.), Textbook of Clinical Cariology (2. Aufl.). Munksgaard, Kopenhagen. (kein DOI verfügbar, Buchkapitel)
- Bardow A, Moe D, Nyvad B, Nauntofte B (2000). The buffer capacity and buffer systems of human whole saliva measured without loss of CO2. Archives of Oral Biology, 45(1):1-12. doi:10.1016/S0003-9969(99)00119-3

## Aufruf

```bash
python3 scripts/analysis/manual/analyse_saliva_ph.py
python3 scripts/analysis/manual/analyse_saliva_ph.py --plot
python3 scripts/analysis/manual/analyse_saliva_ph.py --from 2026-01-01
python3 scripts/analysis/manual/analyse_saliva_ph.py --no-llm
```
