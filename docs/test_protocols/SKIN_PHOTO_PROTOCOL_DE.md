<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# Hautläsion fotografieren — Mess- und Aufnahmeprotokoll

> **English version:** [SKIN_PHOTO_PROTOCOL.md](SKIN_PHOTO_PROTOCOL.md)
> **Import-Workflow & Triage:** [SKIN_LESION_TRACKING_DE.md](SKIN_LESION_TRACKING_DE.md)

Ein konsistentes Aufnahmeprotokoll macht Fotos einer Läsion über Monate/Jahre
hinweg tatsächlich vergleichbar — für den eigenen Verlauf, für den Hautarzt,
und für App-/KI-gestützte Einschätzungen (Skinscreener, VLM-Fotocheck). Ohne
Standardisierung ist weder Größenwachstum noch Farbveränderung objektiv
feststellbar, und Aufnahme-Artefakte (Blitzreflexion, Kompression) können mit
echten Läsionsmerkmalen verwechselt werden.

**Warum das wichtig ist:** Aufnahme-Artefakte wie Blitzreflexionen oder
JPEG-Kompression können auf einem Foto wie klinisch relevante
Läsionsmerkmale aussehen (dunkle Flecken, scheinbare Farbveränderungen) —
mit entsprechend unnötiger Verunsicherung, bis sich der Befund als
Aufnahmefehler statt echter Veränderung herausstellt. Genau solche
Fehleinschätzungen soll dieses Protokoll verhindern.

## 1. Maßstab/Referenz

- **Lineal oder kleines Maßband** direkt neben die Läsion legen, in derselben
  Bildebene — sonst ist Wachstum über die Zeit nicht objektiv vergleichbar.
- Optional: eine kleine Graukarte/Farbreferenzkarte daneben legen — macht
  Farbveränderungen zwischen Aufnahmen mit unterschiedlicher Beleuchtung
  vergleichbar.

## 2. Abstand & Zoom

- **Kein digitaler Zoom** — verschlechtert die tatsächliche Detailauflösung.
  Stattdessen physisch näher herangehen (Makromodus nutzen, falls vorhanden).
- **Zwei Aufnahmen pro Sitzung:**
  - Übersichtsaufnahme (~30 cm) — zeigt Körperstelle/Kontext (wo genau am
    Körper, Bezug zu Muttermalen/Landmarken in der Nähe)
  - Nahaufnahme (~10–15 cm) — Läsion füllt das Bild mit etwas Rand drumherum

## 3. Licht

- **Kein Blitz.** Blitzlicht erzeugt harte Reflexionen und Schlagschatten und
  kann Artefakte erzeugen, die mit echten Läsionsmerkmalen verwechselt werden.
- **Gleichmäßiges, indirektes Tageslicht** bevorzugt (z. B. am Fenster, nicht
  direkte Sonne).
- Wichtiger als "hell" ist **"gleichbleibend"** — nach Möglichkeit immer zur
  ähnlichen Tageszeit / am selben Ort fotografieren, damit Aufnahmen über
  Monate hinweg vergleichbar bleiben.

## 4. Format

- **HEIC oder RAW statt komprimiertem JPEG**, wo möglich — weniger
  Kompressionsartefakte, mehr tatsächliche Bilddetails.
- Falls nur JPEG verfügbar ist: höchste Qualitätsstufe der Kamera-App
  einstellen (keine "kleine Dateigröße"-Option).

## 5. Winkel/Position

- Kamera möglichst **senkrecht über der Läsion**, nicht schräg — eine
  verzerrte Perspektive verfälscht Form- und Größeneinschätzung (relevant für
  Asymmetrie-Bewertung nach ABCDE-Kriterien).

## 6. Optionales Zubehör: von Clip-on-Linse bis DSLR-Makro-Setup

**Einfache Clip-on-Makrolinsen (günstig, ~10–20€):** näherer Fokusabstand,
mehr Detail — aber billige Linsen erzeugen oft Verzerrung, Farbsäume
(chromatische Aberration) und Randunschärfe. Kann dasselbe Problem erzeugen
wie ein Blitzartefakt: ein optisches Artefakt der Linse wird für ein echtes
Läsionsmerkmal gehalten. Bei starker Vergrößerung zudem sehr geringe
Schärfentiefe ohne Stativ.

**Polarisierte Dermatoskop-Aufsätze (Alltags-Empfehlung):** Kreuzpolarisiertes
Licht eliminiert Oberflächenreflexionen und macht subkutane Strukturen
sichtbar (Pigmentnetz, Gefäßmuster, "blau-weißer Schleier") — genau die
Merkmale, nach denen Dermatolog:innen mit dem Auflichtmikroskop suchen, und
die auf normalen Fotos unsichtbar sind. Löst das Blitzreflex-Problem an der
Wurzel, statt es nur zu vermeiden.

- **DermLite HÜD 2** (~99–195 USD je nach Anbieter) — speziell für
  Heim-Monitoring konzipiert, von DermLite/3Gen, dem etablierten Hersteller
  professioneller Dermatoskope (dieselben Geräte, die Hautärzt:innen selbst
  verwenden). Unterstützt Live-Video-Streaming für Telederm-Konsultationen,
  keine Cloud-Bindung. **Bestellt** — nach Vergleich gegen Scaut
  (multispektral, keine Polarisation), IBOOLO DE-500 (~399 USD, polarisiert +
  UV, aber 90€ teurer bei vergleichbarer/leicht schwächerer Bildqualität laut
  unabhängigen Reviews) und MoleScope II (~399€, polarisiert, aber
  Cloud-Zwang via DermEngine).
- **IBOOLO DE-500** (~399 USD) — zusätzlich UV-Modus (365nm, für
  Pilzinfektionen/Pigmentstörungen, für Melanom-Verlauf nicht kernrelevant),
  Metallgehäuse, Magnetadapter — falls die Zusatzmodi wichtiger sind als der
  Preisunterschied.

**Thermalkamera-Aufsatz (FLIR One, Seek Thermal) — Ergänzung, kein Ersatz:**
Wärmebild statt/neben Foto. Macht Entzündungsherde sichtbar (Rosacea-Flares,
lokale Infektionen, entzündetes Gewebe ist oft wärmer), potenziell auch
Durchblutungsstörungen (Raynaud-artige Muster). Kein Polarisationsprinzip,
löst also nicht das Dermoskopie-Problem, sondern liefert eine zusätzliche,
andersartige Information.

**DSLR + Makroobjektiv + Ringblitz mit Kreuzpolfilter (höchste Qualität,
mehr Aufwand):** Ein gebrauchtes DSLR-Gehäuse mit
Makroobjektiv (z. B. Nikon 60mm f/2.8G Micro oder 105mm f/2.8G VR Micro,
beide 1:1-Abbildungsmaßstab) liefert deutlich mehr Detailauflösung als
Handykamera + Dermatoskop-Aufsatz, weil ein echter Kamerasensor statt einer
Telefonkamera dahintersteckt. Ein normaler Ringblitz ist aber **nicht
polarisiert** — dasselbe Reflexions-Risiko wie beim einfachen Blitz (s.
Abschnitt 3). Lösung: **Kreuzpolarisations-Setup** — linearer Polfilter vors
Objektiv, Polfolie auf den Ringblitz, beide um 90° zueinander gedreht.
Eliminiert Oberflächenreflexe nach demselben Prinzip wie ein
Dermatoskop-Aufsatz, nur mit höherwertigem Sensor. Polfolie als
Zuschnitt-Rollenware im Fotobedarf erhältlich, Polfilter fürs Objektiv ist
Standardzubehör. **RAW-Format (NEF bei Nikon)** wird direkt
von `import_skin.py` unterstützt (Original bleibt erhalten, PII-Metadaten
werden entfernt, zusätzlich eine JPEG-Vorschau erzeugt — s.
`scripts/modules/imaging_utils.py`). Mehr Aufwand pro Aufnahme (Kamera
aufbauen statt Handy zücken) — eher für wichtige Verlaufs-Meilensteine (z. B.
Nachsorge-Termine alle 3 Monate) als für den Alltag geeignet, ergänzend zum
DermLite, nicht als Ersatz.

Wichtig bei allen Aufsätzen: Immer zusätzlich ein normales Übersichtsfoto
**ohne** Aufsatz machen — Nahaufnahmen verlieren den Körper-Kontext.

Preise und Verfügbarkeit ändern sich — vor Kauf aktuelle Angebote prüfen.

## 7. Selbstbeobachtung: ABCDE-Regel

Die ABCDE-Regel ist das Standard-Screening-Raster für Pigmentläsionen (u. a.
von der Deutschen Krebsgesellschaft/ADO empfohlen). Sie ersetzt keine
ärztliche Beurteilung, hilft aber dabei, beim Fotovergleich systematisch auf
dieselben Merkmale zu achten statt auf ein diffuses Gesamtgefühl:

- **A — Asymmetrie:** Ist die Läsion bei gedachter Mittellinie in zwei
  Hälften unregelmäßig, nicht spiegelbildlich?
- **B — Begrenzung:** Ist der Rand unscharf, gezackt oder ausgefranst statt
  glatt und gleichmäßig?
- **C — Colorit (Farbe):** Mehrere Farbtöne in derselben Läsion (z. B.
  Braun-, Schwarz-, Rot-, Grau- oder Blauanteile gemischt) statt einheitlich
  einfarbig?
- **D — Durchmesser:** Größer als ca. 5 mm (Referenz: Bleistift-Radiergummi)?
  Absolutwert weniger entscheidend als Veränderung — dafür ist der Maßstab
  aus Abschnitt 1 da.
- **E — Entwicklung:** Veränderung im Verlauf — Wachstum, neue Erhabenheit,
  Farbwechsel, Juckreiz/Bluten? Das ist der Grund, warum dieses Protokoll
  überhaupt existiert: ohne vergleichbare Fotos ist "E" nicht objektiv zu
  beurteilen.

Ein einzelnes zutreffendes Kriterium ist kein Beweis, mehrere zutreffende
Kriterien kein Ausschluss — die Regel ist ein **Anlass, zeitnah ärztlich
abklären zu lassen**, keine Diagnose. Bei Unsicherheit gilt: **lieber einmal
mehr als einmal weniger** beim Hautarzt vorstellen. Und: egal, ob die
Krankenkasse die Untersuchung zahlt oder nicht — **Prävention rettet
Menschenleben und erspart Leiden.**

**Appell:** Lass dich regelmäßig (mind. einmal im Quartal) von Partner:in
oder guten Freund:innen auf schwer einsehbare Körperstellen (Rücken,
Kopfhaut, Nacken) untersuchen — das eigene Auge und der Spiegel erreichen
nicht überall hin. Und spätestens alle zwei Jahre zur
Hautkrebsvorsorge-Screening beim Hautarzt, unabhängig davon, ob gerade etwas
auffällig erscheint.

**Über das Standard-Screening hinaus:** frag nach, ob dein:e Hautärzt:in
**Videodermatoskopie** anbietet (digitale, vergrößerte, speicherbare Bilder
pro Läsion — deutlich empfindlicher für subtile Veränderungen über die Zeit
als eine Blickdiagnose) oder, noch besser, **Ganzkörper-Mapping**
(systematische fotografische Dokumentation der gesamten Hautoberfläche, sodass
neue oder sich verändernde Läsionen gegen eine Baseline auffallen, statt sich
auf Erinnerung zu verlassen) — zunehmend mit **KI-gestütztem Abgleich**
zwischen Terminen angeboten, um Veränderungen zu markieren, die ein
menschlicher Blick übersehen könnte. Nicht überall verfügbar oder von der
Kasse übernommen, und ersetzt nicht die eigene fachärztliche Einschätzung,
aber eine Nachfrage wert bei Risikofaktoren (viele Muttermale, eigene oder
familiäre Melanom-Vorgeschichte, frühere atypische Befunde).

## Kurz-Checkliste vor jedem Foto

- [ ] Lineal/Maßstab neben der Läsion?
- [ ] Kein digitaler Zoom, stattdessen näher ran?
- [ ] Übersichts- **und** Nahaufnahme gemacht?
- [ ] Kein Blitz, gleichmäßiges Licht?
- [ ] HEIC/RAW statt komprimiertem JPEG?
- [ ] Kamera senkrecht über der Läsion?
- [ ] ABCDE-Kriterien beim Vergleich mit früheren Fotos durchgegangen?

## Import

Fotos anschließend wie gewohnt importieren:

```bash
python3 scripts/importers/import_skin.py foto.jpg --location "linke Großzehe"
python3 scripts/importers/import_skin.py folgefoto.jpg --lesion-id 3
```

Details zum Importer: `docs/de/importers/import_skin.md` (generiert aus dem
Skript-Docstring).
