# generate_patient_summary.py - Patienten-Übersicht als OpenOffice-Writer-Dokument

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/exporters/generate_patient_summary.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Fasst die manuell gepflegten Kyoro-Konfig-JSON-Dateien (Familien- anamnese, Vorerkrankungen, Medikamente, Impfungen, Operationen) sowie aktuelle Medikationsstatus aus medicine.db in einem druckfertigen ODT-Fließtext-Dokument zusammen.

## Relevanz

Reduziert wiederholtes Von-Hand-Ausfüllen von Anamnesebögen bei jedem Arztbesuch

## Methode

Liest dieselben JSON-Quellen wie export_arzt_komplett.py, baut daraus Abschnitte mit Überschrift + Stichpunktliste über odfpy (OpenDocumentText) statt Tabellenblättern. Keine Diagnose- oder Personennamen im Quellcode — alle Inhalte kommen zur Laufzeit aus KYORO_CONFIG_DIR.

## Datenfluss

- **Liest:** `~/.config/kyoro/family_history.json`, `clinical_events.json`, `medication_history.json`, `medicine.db::medications`
- **Schreibt:** `<output>.odt - Patientenübersicht als Fließtext`

## Grenzen

Abschnitte ohne strukturierte Kyoro-Quelle (Notfallkontakt, GdB, Patientenverfügung, Implantate) werden als auszufüllende Platzhalter ausgegeben, nicht automatisch befüllt. --language stellt den Text des Dokuments um; Einträge aus Config und medicine.db bleiben in der Sprache, in der sie erfasst wurden.

## Aufruf

```bash
python3 scripts/exporters/generate_patient_summary.py
python3 scripts/exporters/generate_patient_summary.py --output intern/patientenuebersicht.odt
python3 scripts/exporters/generate_patient_summary.py --language en
```
