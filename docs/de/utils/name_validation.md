# name_validation — Generisches Namensvalidierungs- und Erkennungsmodul

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/utils/name_validation.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Bietet Funktionen zur Erkennung und Validierung von Namen unter Verwendung der Konfiguration aus name_lists.json.Arbeitet mit dem Pseudonymisierungssystem zusammen, um potenziell persönliche Informationen in Textdaten zu identifizieren. Hauptfunktionen: Erkennung häufiger deutscher Vor- und Nachnamen, Identifizierung von Namensmustern (z.B. "Vorname Nachname"), Validierung von Namensformaten, Integration mit dem Pseudonymisierungssystem.

## Relevanz

Bietet Hilfsfunktionen für die Datenverarbeitung, essentiell für die Systemfunktionalität

## Methode

Lädt Namenslisten aus name_lists.json im utils/ Verzeichnis oder verwendet eingebaute Fallback-Listen. Nutzt reguläre Ausdrücke für effiziente Mustererkennung. Die NameDetector-Klasse bietet Methoden für: Einzelne Vor-/Nachnamen prüfen, Vollständige Namen erkennen, Titel+Name-Kombinationen erkennen, umfassende Namenserkennung in Texten, person_id-Validierung. Ein Singleton-Objekt (detector) wird für einfache Nutzung bereitgestellt.

## Datenfluss

- **Liest:** `scripts/utils/name_lists/name_lists.json`
- **Schreibt:** `(keine Schreiboperationen)`

## Grenzen

Erkennt nur in den Namenslisten konfigurierte Namen. Case-insensitive Vergleich für bessere Trefferquote. Verarbeitet keine echten Personendaten - dient nur der Erkennung von Mustern.

## Aufruf

```bash
from utils.name_validation import NameDetector, is_common_first_name, detect_names_in_text
detector = NameDetector()
# Einzelne Namen prüfen
is_first = is_common_first_name("Anna")
is_last = is_common_last_name("Müller")
# Umfassende Erkennung in Text
names = detect_names_in_text("Dr. med. Anna Müller war hier")
# Person-ID validieren
valid = detector.validate_person_id("user_123")
```
