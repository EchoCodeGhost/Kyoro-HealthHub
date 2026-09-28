<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# Hautläsionen — Tracking-Workflow

> **English version:** [SKIN_LESION_TRACKING.md](SKIN_LESION_TRACKING.md)

Für die Aufnahmetechnik selbst siehe [SKIN_PHOTO_PROTOCOL_DE.md](SKIN_PHOTO_PROTOCOL_DE.md) —
dieses Dokument behandelt den Workflow rund um Import, Verlaufsverfolgung
und Triage einer bereits aufgenommenen Läsion.

**Importer:** `python3 scripts/importers/import_skin.py`
**Analyse:** VLM (ABCDE-Kriterien + Triage-Empfehlung) via OpenRouter
**DB:** `medicine_imaging.db` → `skin_lesions` + `imaging_files`

---

## Retrospektive Läsionshistorie aus alten Fotos

Falls eine Läsion beim Hautarzttermin schon länger besteht, aber nie
systematisch fotografiert wurde: Fotoalben/Cloud-Fotos (Google Fotos, Apple
Fotos, alte Handy-Backups) können trotzdem einen groben Zeitverlauf
liefern — Urlaubsfotos, Familienfotos, Fitness-/Spiegel-Selfies zeigen die
betroffene Hautstelle oft unbeabsichtigt mit.

**Vorgehen:**
1. In der Fotos-App nach Aufnahmeort/-zeitraum filtern (z. B. "Strand",
   "Schwimmbad", "Sommer 2023") — Fotos mit unbedeckter Haut sind
   wahrscheinlicher
2. Für jeden brauchbaren Fund: **Aufnahmedatum aus den EXIF-Metadaten**
   notieren (verlässlicher als die eigene Erinnerung)
3. Ausschnitt der Läsion aus dem alten Foto zuschneiden/vergrößern, so gut
   die Auflösung es hergibt
4. Import mit dem **tatsächlichen historischen Aufnahmedatum** (`--date`),
   nicht dem heutigen Datum:
   ```bash
   python3 scripts/importers/import_skin.py altes_foto_ausschnitt.jpg \
     --lesion-id 1 --date 2023-07-15 --source other
   ```

**Wichtig — Erwartungen an die Bildqualität:** Alte Handyfotos sind meist
nicht für dermatologische Zwecke aufgenommen (falscher Winkel, kein
Maßstab, schlechte Auflösung, evtl. Kompressionsartefakte). Das VLM kann
solche Fotos trotzdem grob einordnen, aber die Aussagekraft ist geringer
als bei einem nach [SKIN_PHOTO_PROTOCOL_DE.md](SKIN_PHOTO_PROTOCOL_DE.md)
aufgenommenen Foto. Der Wert liegt vor allem in der **Zeitangabe** ("gab es
das schon vor zwei Jahren?"), weniger in der Detailbeurteilung.

**Für den Hautarzt besonders wertvoll:** Ein klar datierbares altes Foto
kann die Frage "seit wann besteht das?" objektiv beantworten, statt auf
Erinnerung angewiesen zu sein — das kann bei der Einschätzung, ob eine
Veränderung erst kürzlich begann (Kriterium E in ABCDE), den Unterschied
machen.

---

## Unterstützte Quellen

| Quelle | `--source` | Qualität | Hinweise |
|---|---|---|---|
| Smartphone-Kamera (direkt) | `camera` | gut | AirDrop/USB auf Rechner |
| Screenshot aus Skin-Scanner-App | `screenshot` | gut | App-Score sichtbar im Bild |
| DSLR + Makroobjektiv | `dslr` | sehr gut | Beste Detailauflösung |
| Andere | `other` | variabel | — |

---

## Workflow

### Erste Aufnahme einer neuen Läsion

```bash
python3 scripts/importers/import_skin.py foto.jpg \
  --location "Rücken links, ca. 5cm unterhalb Schulterblatt" \
  --date 2026-01-15 \
  --source camera
```

→ Neue Läsion angelegt: **ID 1**

### VLM-Analyse anstoßen (separater Schritt)

Der Import selbst führt keine Bildanalyse durch — dafür `analyse_skin.py`:

```bash
python3 scripts/analysis/manual/analyse_skin.py --analyse
```

→ Analysiert alle noch nicht ausgewerteten Fotos, Triage-Ergebnis erscheint
→ Bericht landet unter `analyses/manual/`

### Folgefoto (gleiche Läsion)

```bash
python3 scripts/importers/import_skin.py folgefoto.jpg \
  --lesion-id 1 --date 2026-04-15
```

### App-Score nachtragen (z.B. nach Skin-Scanner-Auswertung)

```bash
python3 scripts/importers/import_skin.py \
  --update-lesion 1 --app-score mittel --app-name "Skin-Scanner-App"
```

### Hautarzt-Befund eintragen

```bash
python3 scripts/importers/import_skin.py \
  --update-lesion 1 \
  --derm-assessment "Klinisch unauffällig, Kontrolle in 12 Monaten" \
  --derm-date 2026-04-20
```

### OP + Histologie eintragen

```bash
python3 scripts/importers/import_skin.py \
  --update-lesion 1 \
  --operated --operation-date 2026-05-01 \
  --histology "[Histologie-Ergebnis]" --histology-subtype "[Subtyp]" \
  --histology-date 2026-05-08
```

### Alle Läsionen auflisten

```bash
python3 scripts/importers/import_skin.py --list-lesions
```

---

## Triage-Ampel

| Symbol | Bedeutung | Handlung |
|---|---|---|
| 🔴 Sofort | Hochgradig verdächtig — ABCDE mehrfach auffällig | Dermatologe innerhalb 1–2 Wochen |
| 🟡 Zeitnah | Einzelne Auffälligkeiten | Dermatologe innerhalb 4–8 Wochen |
| 🟢 Verlauf | Unauffällig, aber Monitoring empfohlen | Selbst-Foto in 6–12 Monaten, Dermatologe bei Änderung |
| ✅ Unauffällig | Kein Anlass zur Sorge | Keine Aktion |
| ❓ Bildqualität | Foto zu unscharf/dunkel für Beurteilung | Besseres Foto aufnehmen |

**Wichtig:** Das VLM ist kein Ersatz für eine dermatologische Untersuchung. Bei 🔴 oder 🟡 immer zum Hautarzt — unabhängig vom App-Score.

---

## Körperstellen-Kurzreferenz (für `--location`)

Freitext ist möglich, aber konsistente Bezeichnungen helfen beim Tracking:

```
Gesicht: "Wange links", "Nasenrücken", "Stirn rechts", "Unterlippe"
Kopf:    "Scheitel", "Hinterkopf links", "Schläfe rechts"
Hals:    "Hals vorne", "Nacken links"
Rumpf:   "Brust Mitte oben", "Rücken links oben", "Rücken rechts unten", "Schulter rechts"
         "Bauch links", "Flanke rechts", "Steißbein"
Arme:    "Oberarm links außen", "Unterarm rechts innen", "Handrücken rechts"
Beine:   "Oberschenkel rechts innen", "Unterschenkel links vorne", "Fußrücken links"
Genital: nach Bedarf
```

---

## ABCDE-Selbstprüfung (für die Aufnahme)

Wenn du beim Fotografieren diese Fragen mit „Ja" beantwortest → unbedingt VLM-Analyse (Details zur Regel: [SKIN_PHOTO_PROTOCOL_DE.md](SKIN_PHOTO_PROTOCOL_DE.md#7-selbstbeobachtung-abcde-regel)):

- **A:** Ist eine Hälfte anders als die andere?
- **B:** Ist der Rand ausgefranst, unregelmäßig, verwaschen?
- **C:** Mehr als eine Farbe (braun/schwarz/rot/weiß)?
- **D:** Größer als ein Radiergummi (~6 mm)?
- **E:** Hat sich die Läsion in letzter Zeit verändert (Farbe, Größe, Form, Jucken, Bluten)?

---

> **Hinweis für behandelnde Ärzte:** Vollständige Vorbefunde, Medikationsverlauf und Wearable-Langzeitdaten sind in der **elektronischen Patientenakte (ePA)** hinterlegt. Bitte Zugriff über die TI-Anbindung Ihrer Praxissoftware anfordern.
