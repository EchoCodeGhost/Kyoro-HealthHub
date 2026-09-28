# Produkt-Inhaltsstoff-Lookup via Open Beauty Facts + Open Products Facts + Open Food Facts + PubChem + Claude Vision.

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/utils/lookup_ingredients.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Ermöglicht das Nachschlagen von Produkt-Inhaltsstoffen aus mehreren Datenbanken: Open Beauty Facts (Kosmetik), Open Products Facts (Haushaltsprodukte), Open Food Facts (Lebensmittel/Kosmetik-Grenzfälle), sowie optionale Anreicherung mit PubChem-Daten (chemische Eigenschaften, GHS-Klassifikation). Falls kein Text verfügbar ist, wird das Produktfoto heruntergeladen und per Vision-LLM analysiert.

## Relevanz

Ermöglicht die Suche und Referenzierung von Daten, essentiell für die Datenintegration

## Methode

Erweiterte Lookup-Reihenfolge: 1. Open Beauty Facts (Text) 2. Open Products Facts (Text) — Fallback für Haushaltsprodukte 3. Open Food Facts (Text) — Fallback für Lebensmittel-Kosmetik-Grenzfälle 4. Vision-Fallback (Foto) — für alle Datenbanken 5. PubChem-Anreicherung (optional) — für jeden gefundenen INCI-Namen Konsistentes Allergen-Matching gegen lokale Referenztabellen (ECHA-SVHC, CosIng) und handkuratierte KNOWN_ALLERGENS-Liste.

## Datenfluss

- **Liest:** `Open`, `Beauty`, `Facts`, `API`, `Open`, `Products`, `Facts`, `API`, `Open`, `Food`, `Facts`, `API`, `PubChem`, `API`, `(optional)`, `Produktfotos`
- **Schreibt:** `Keine Tabellen (gibt Inhaltsstoff-Daten zurück), data/reference/*.csv (lokal)`

## Grenzen

Abhängig von der Datenqualität der verschiedenen APIs und Vision-Genauigkeit. PubChem-Abfragen können für exotische Inhaltsstoffe fehlschlagen. Referenztabellen (ECHA/CosIng) müssen lokal gepflegt werden. Erkennt einen spezifischen, real beobachteten Datenfehler: wenn OBF/OPF/OFFs `ingredients_text` an manchen Stellen keine Kommas zwischen einzelnen INCI-Namen hat, klebt sowohl der Rohtext-Split als auch OBF's eigene "strukturierte" ingredients-Liste mehrere Namen zu einem Eintrag zusammen — und der bisherige >80-Zeichen- Filter warf solche zusammengeklebten Einträge unbemerkt komplett weg, statt sie zu melden. Beide Symptome (verdächtig lange, kommalose Mehrwort-Einträge; verworfene Übergroß-Einträge) lösen jetzt eine `data_quality_warning` aus und triggern bei aktiviertem Vision-Fallback automatisch einen Foto-Gegencheck. Diese Erkennung ist heuristisch (Wortanzahl/Länge) und deckt nicht jede denkbare Form von Quelltext-Korruption ab.

## Aufruf

```bash
python lookup_ingredients.py
python lookup_ingredients.py --help
python lookup_ingredients.py "Elmex Gelee" --no-pubchem
python lookup_ingredients.py --barcode 8718951466043 --no-vision
```
