# update_icd10_catalog.py — ICD-10-GM-Katalog lokal installieren/aktualisieren

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/utils/update_icd10_catalog.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Installiert oder aktualisiert den lokalen ICD-10-GM-Katalog (data/reference/icd10gm/), den scripts/modules/icd10_catalog.py zum Validieren von ICD-Codes und zum Code↔Text-Plausibilitäts- Check nutzt. Der Katalog wird NICHT im Repo gebündelt (siehe Moduldocstring von icd10_catalog.py @limits) -- jede Installation muss diesen Downloadschritt selbst einmal durchlaufen.

## Relevanz

Hält den lokalen ICD-10-GM-Katalog aktuell, essentiell dafür, dass der Code↔Text-Plausibilitätscheck nicht gegen eine veraltete Jahresversion prüft

## Methode

Drei Modi: --check fragt nur die BfArM-Downloadseite ab und vergleicht die dort gefundene neueste Jahresversion mit der lokal installierten (aus dem Dateinamen in data/reference/ icd10gm/), OHNE etwas herunterzuladen oder Bedingungen zu akzeptieren. --download führt den tatsächlichen Download durch: BfArM verlangt PRO NUTZER*IN die explizite Zustimmung zu einem Nutzungsvertrag (Downloadbedingungen) -- dieses Skript zeigt daher vor jedem Download eine Kurzfassung der Bedingungen und verlangt eine explizite Bestätigung (interaktiv per Eingabe oder via --accept-terms für nicht-interaktive Läufe), NIE eine automatische/stellvertretende Zustimmung. Die aktuelle Download-URL wird NICHT für ein festes Jahr hartkodiert, sondern bei jedem Lauf frisch aus der BfArM-Downloadseite herausgelesen (Regex auf "icd10gmJJJJsyst-meta_zip.html") -- damit funktioniert --download auch nächstes Jahr ohne Codeänderung, solange BfArM das URL-Schema beibehält. --from-zip <pfad> überspringt den Download komplett: für Nutzer*innen, die die ZIP bereits manuell im Browser heruntergeladen (und die Bedingungen dort akzeptiert) haben. In allen Fällen wird aus der ZIP nur Klassifikationsdateien/icd10gmJJJJsyst_kodes.txt entpackt (die Code+Titel-Liste, siehe icd10_catalog.py) -- der Rest (Mortalitäts- listen, PDFs, Alphabet-Verzeichnis) wird verworfen, um data/reference/icd10gm/ klein zu halten; dieselbe Datei wird UNVERÄNDERT übernommen (kein Textumbau -- siehe Urheberrechts-Änderungsverbot, § 62 UrhG, in den BfArM- Downloadbedingungen).

## Datenfluss

- **Liest:** `https://www.bfarm.de/.../Kodiersysteme/Services/Downloads/`, `(online`, `nur`, `--check`, `und`, `--download)`
- **Schreibt:**

  ```
  data/reference/icd10gm/icd10gmJJJJsyst_kodes.txt (unveränderte
  Kopie aus der BfArM-ZIP); data/reference/icd10gm/NOTICE.txt
  (Pflicht-Quellenangabe nach § 63 UrhG, siehe
  Downloadbedingungen-Anhang)
  ```

## Grenzen

Das BfArM-Seitenlayout/URL-Schema kann sich ändern -- schlägt dann mit einer klaren Fehlermeldung fehl (kein Codeänderungs- bedarf garantiert). Prüft NICHT automatisch auf ICD-11 -- die BfArM-Downloadseite bietet aktuell nur ICD-10-GM/OPS/ICD-10-WHO/ Alpha-ID-SE/ICD-O-3/ICF an; --check gibt dazu nur einen statischen Hinweis aus, kein Live-Signal, ob/wann Deutschland auf ICD-11 zur Abrechnung umstellt (das ist Stand dieses Projekts keine automatisch beobachtbare Tatsache).

## Aufruf

```bash
python3 update_icd10_catalog.py --check
python3 update_icd10_catalog.py --download --accept-terms
python3 update_icd10_catalog.py --from-zip ~/Downloads/icd10gm2026syst-meta.zip
```
