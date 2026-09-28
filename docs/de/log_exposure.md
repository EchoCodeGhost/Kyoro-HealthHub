# log_exposure.py — Manuelles Expositions-Log für Allergene und Reizstoffe

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/log_exposure.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Erfasst Expositionen gegenüber nicht-nahrungsmittelbasierten Allergenen und Reizstoffen für die spätere Analyse. Ermöglicht das Nachschlagen von Inhaltsstoffen über Open Beauty Facts und das Verknüpfen mit Symptomen.

## Relevanz

Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung

## Methode

Unterstützt verschiedene Kategorien: Medikamente, Kosmetik, Zahnpflege, Haushaltsmittel, Sonnenschutz, Nahrungsergänzung, Umweltallergene. Daten werden in der exposures Tabelle gespeichert. Substanz-Hinweise können pro Kategorie abgefragt werden. Analyse via analyse_product_exposures.py.

## Datenfluss

- **Liest:** `exposures`, `Tabelle`
- **Schreibt:** `exposures Tabelle`

## Grenzen

Keine Validierung der Kategorie-Codes. Expositionen ohne Datum werden uebersprungen.

## Aufruf

```bash
python log_exposure.py lookup "Elmex Gelee"
python log_exposure.py lookup "Dior Sauvage"
python log_exposure.py add --category dental --product "Colgate Total" --lookup
python log_exposure.py add --category medication --product "Ibuprofen 400" --substance "Ibuprofen"
python log_exposure.py list
python log_exposure.py list --days 14
python log_exposure.py hints
python log_exposure.py delete 42
```
