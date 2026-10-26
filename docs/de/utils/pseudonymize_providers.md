# pseudonymize_providers.py — Arztpraxis- und Labornamen in der Datenbank pseudonymisieren

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/utils/pseudonymize_providers.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Ersetzt echte Arztpraxis- und Labornamen in health.db und medicine.db durch stabile Pseudonyme (Labor-1A2B3C4D) und entfernt Postadressen aus Freitext-Spalten der Laborbefunde. Läuft vollständig lokal.

## Relevanz

Verhindert, dass Arztpraxis- und Labornamen oder Adressen im Datenbestand stehen, der exportiert oder an externe Dienste gegeben wird

## Methode

Spalten laut Tabelle _SPECS (lab_manual.labor, lab_results.labor, …) werden Zeile für Zeile umgeschrieben. Das Pseudonym ist ein SHA-256-Kurzhash des normalisierten Namens, damit derselbe Name immer dasselbe Pseudonym bekommt. Die Zuordnung Pseudonym zu Klartext liegt nur in identity.db (provider_pseudonym_map), außerhalb der Gesundheitsdatenbank. Kollidiert ein umbenannter lab_manual-Schlüssel mit einer vorhandenen Zeile, bleibt die vorhandene Zeile bestehen. Bereits pseudonymisierte Werte werden übersprungen (idempotent).

## Datenfluss

- **Liest:** `health.db`, `medicine.db`, `(Tabellen`, `aus`, `_SPECS`, `sofern`, `vorhanden)`
- **Schreibt:** `health.db, medicine.db, identity.db (provider_pseudonym_map)`

## Grenzen

Nur die Spalten aus _SPECS. Arztpraxis- oder Labornamen in beliebigem Freitext werden nicht erkannt. Die Pseudonymisierung ist nicht umkehrbar ohne identity.db; wer identity.db verliert, kann Pseudonyme nicht mehr auflösen. Eine bereits exportierte oder gesicherte Datenbank bleibt unverändert.

## Aufruf

```bash
python -m utils.pseudonymize_providers --dry-run
python -m utils.pseudonymize_providers
```
