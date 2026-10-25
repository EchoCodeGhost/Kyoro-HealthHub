# name_redaction.py — Personennamen in Freitext erkennen und entfernen

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/modules/name_redaction.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Erkennt Personennamen in Text (Namen mit Anrede oder Titel, Namen hinter Feldbezeichnern wie "Name:", bekannte Namen der Person und ihrer Angehörigen, häufige Vor- und Nachnamen) und ersetzt sie durch einen Platzhalter. Ergänzt address_redaction für Bilder und PDFs.

## Relevanz

Verhindert, dass Namen von Patientinnen, Patienten, Angehörigen und Behandelnden aus Befunden und Fotos in Ablage, Exporte oder externe Dienste gelangen

## Methode

Reguläre Ausdrücke für: Anrede/Titel plus Name (Dr., Prof., Dr. med., Anredewörter …), Feldbezeichner plus Name (Name, Patient, Versicherte, "Name, Vorname"), Vorname aus der Liste plus Großwort, Großwort plus Nachname aus der Liste. Bekannte Namen stammen aus health_config.json (privacy_check.patient_names), aus identity.db (person_name_map: Name und Aliase) und aus dem Aufrufer; jede Namensteil-Zeichenkette ab drei Buchstaben wird als ganzes Wort ohne Beachtung der Groß-/Kleinschreibung entfernt. Benachbarte Treffer werden zu einem Platzhalter verschmolzen.

## Datenfluss

- **Liest:** `~/.config/kyoro/health_config.json`, `(privacy_check.patient_names`, `optional)`, `identity.db`, `(person_name_map`, `optional)`, `scripts/utils/name_lists/name_lists.json`
- **Schreibt:** `Keine (reine Textfunktionen)`

## Grenzen

Heuristik, keine Garantie: Namen ohne Anrede, Titel, Feldbezeichner oder Eintrag in den bekannten Namen (z. B. "Max Muster hat angerufen") werden nicht erkannt. Kurze Namensteile (unter drei Buchstaben) werden nicht einzeln entfernt. Bekannte Namen, die zugleich normale Wörter sind, entfernen auch diese Wörter. Schlechte OCR kann Namen verfehlen. Namen von Praxen und Laboren sind kein Ziel dieses Moduls.

## Aufruf

```bash
from modules.name_redaction import redact_names, find_name_spans
redact_names("Dr. med. Muster, Kardiologie")
redact_names("Notiz zu Erika", extra_names=["Erika Mustermann"])
```
