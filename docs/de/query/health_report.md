# Gesundheitsbericht Generator — KI-generierte Gesundheitsberichte für Check-ups

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/query/health_report.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Erstellt strukturierte Gesundheitsberichte im Markdown-Format für Gesundheits-Check-ups. Fasst alle wichtigen Gesundheitsmetriken zusammen und ordnet sie ein. Dient als Vorbereitung für medizinische Konsultationen.

## Relevanz

Ermöglicht die Generierung von Gesundheitsberichten, essentiell für die klinische Dokumentation

## Methode

Sammelt Daten aus verschiedenen Tabellen (measurements, blood_pressure, sleep, etc.) und strukturiert sie nach Gesundheitskategorien. Nutzt LLMProvider für die Generierung des freien Textes. Unterstützt Fokus auf bestimmte Bereiche (kardio, schlaf, etc.) und Zeiträume.

## Berechnung

```
Gesundheits-Score basierend auf Abweichung von Normalbereichen und Risikofaktoren
```

## Datenfluss

- **Liest:** `measurements`, `blood_pressure`, `sleep`, `ppi_hrv_advanced`, `sessions`, `symptoms`
- **Schreibt:** `OUT_DIR/health_reports/ (Markdown-Berichte)`

## Grenzen

Heuristische Methode: KI-generiert, ersetzt KEINE medizinische Bewertung. Berichte basieren auf verfügbaren Messdaten und können unvollständig sein. Medizinische Bewertung durch Fachpersonal erforderlich.

## Referenzen

- Singhal K, Azizi S, Tu T et al. (2023). Large language models encode clinical knowledge. Nature, 620(7972):172-180. doi:10.1038/s41586-023-06291-2
- Topol EJ (2019). High-performance medicine: the convergence of human and artificial intelligence. Nature Medicine, 25(1):44-56. doi:10.1038/s41591-018-0300-7

## Aufruf

```bash
python health_report.py                    # Standardbericht (letzte 12 Monate)
python health_report.py --period 2024     # Nur ein Jahr
python health_report.py --focus kardio    # Schwerpunkt Kardiologie
python health_report.py --focus schlaf    # Schwerpunkt Schlaf
python health_report.py --output report.md # Ausgabedatei angeben
```
