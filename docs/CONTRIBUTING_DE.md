# Mitwirken

> **English version:** [CONTRIBUTING.md](CONTRIBUTING.md)

Kyoro-HealthHub nutzt eine modulare Plugin-Architektur. Eine neue Datenquelle, ein neues Export-Profil oder ein neues Gerät hinzuzufügen erfordert keine Änderungen am Kern-Code.

Vor dem Start lohnt ein Blick in [OPENSPEC_DE.md](OPENSPEC_DE.md) — die
architektonischen Anforderungen des Projekts (Pipeline-Reihenfolge,
DB-Schema-Konventionen, Privacy-Regeln, Importer-Pattern) liegen als
versionierte Specs unter `openspec/specs/`, ergänzend zu dieser Anleitung.

---

## Lizenz und Sign-off

Mit deinem Beitrag erklärst du dich einverstanden, dass dein Code unter
[GNU General Public License v3.0 oder später](../LICENSE) veröffentlicht
wird (dieselbe Lizenz wie das Projekt).

Dieses Projekt nutzt das **Developer Certificate of Origin (DCO)** statt eines
Contributor License Agreements. Jeder Commit muss signiert sein:

```bash
git commit --signoff -m "deine nachricht"
```

Dadurch wird eine Zeile `Signed-off-by: Dein Name <du@example.com>` ergänzt,
mit der du bestätigst, dass du den Beitrag selbst geschrieben hast (oder das
Recht hast, ihn unter GPL einzureichen). Voller Text: [developercertificate.org](https://developercertificate.org/).

Neue Quelldateien sollten einen SPDX-Header tragen:

```python
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
```

## Upstream-first-Prinzip

Wer Kyoro-HealthHub verbessert oder erweitert — für ein Forschungsprojekt,
eine klinische Studie oder den eigenen Bedarf — ist herzlich eingeladen,
die Änderungen per Pull Request zurückzubringen.

Das ist keine rechtliche Pflicht unter GPL-3.0, sondern eine Erwartung der
Community. Forschung lebt vom Teilen. Ein privater Fork hilft niemandem;
ein PR nutzt allen Betroffenen und Forschenden, die dieses Werkzeug einsetzen.

Wenn institutionelle Datenschutz- oder Ethikvorgaben einen öffentlichen PR
verhindern, bitte zumindest ein Issue eröffnen, das die Verbesserung
beschreibt — damit andere sie unabhängig umsetzen können.

---

**Bitte keine** Klarnamen, Wohnorte, Geburtsdaten oder echten API-Tokens in
Commits, Issues oder Pull Requests einbringen. Stattdessen Platzhalter-Daten
verwenden.

**Diese Software ist kein Medizinprodukt.** Beiträge, die Ausgaben als
diagnostisch darstellen, klinische Validierung suggerieren die nicht existiert,
oder konkrete medizinische Handlungsempfehlungen an Endnutzer geben, werden
abgelehnt. Siehe [NOTICE](../NOTICE).

Mit deinem Beitrag stimmst du auch den [Ethischen Grundsätzen](ETHICS_DE.md)
des Projekts zu — Menschenwürde, Rechte chronisch Kranker und Behinderter,
LGBTQ+-Schutz, verbotene Nutzungen und Sicherheitsanforderungen.

---

## Git-Workflow

`main` ist ein geschützter Branch: direkte Pushes werden abgelehnt — für
jeden Beitrag, ob menschlich oder KI-unterstützt, auch für Repo-Admins.
Jede Änderung läuft über einen Branch und einen Pull Request:

```bash
git checkout -b <kurzer-beschreibender-branch-name>
# Änderungen machen, committen
git push -u origin <branch-name>
gh pr create --base main   # oder den PR direkt auf github.com öffnen
```

Ein PR wird merge-bar, sobald sein **„Quality gate"**-Check (`ci.yml`, führt
`tools/qa_check.py` aus) grün ist und der Branch auf dem aktuellen Stand von
`main` ist. Es gibt keine Pflicht-Anzahl an Approvals: Dies ist ein kleines,
größtenteils solo-/KI-unterstütztes Projekt (siehe
[CONTRIBUTORS.md](../CONTRIBUTORS.md)) — ein grüner PR kann von jedem mit
Schreibzugriff gemerged werden, niemand muss vorher extra „approven". Sollte
der Kreis der Mitwirkenden wachsen, wird dieser Abschnitt um eine echte
Review-Pflicht ergänzt.

Ein KI-Assistent, der an diesem Repo arbeitet, kann seinen eigenen Pull
Request nicht stellvertretend freigeben — GitHub lehnt eine Freigabe durch
denselben Account ab, der den PR eröffnet hat — daher bleibt das Mergen
auch dann eine menschliche Handlung, wenn ein Assistent den Branch verfasst hat.

## Prüfungen vor einem Pull Request

Führe zuerst das CI-Gate lokal aus — genau das läuft auch in `ci.yml`, ein
lokaler Abgleich erspart einen roten PR:

```bash
python3 tools/qa_check.py
```

Das führt 11 Prüfungen aus: Docs-Synchronität (`tools/gen_docs.py --check`),
Prompts-Docs-Synchronität (`scripts/generate_prompts_docs.py --check`),
SPDX-Header, Syntax, Source-Privacy, keine eingebetteten Daten, keine
Memory-Links, AI-Labeling, ruff (eingeschränktes, nur auf Bugs zielendes
Regelset), Docstrings und Syndrome-Endemic-Regions-Sync. Details zu jeder
Prüfung stehen im Modul-Docstring von `tools/qa_check.py`.

`tests/smoke.sh` ist **nicht** Teil dieses Gates — es deckt von den
Prüfskripten nur `check_sql_columns.py` ab. Die verbindliche Anforderung für
Source-Privacy steht in
[`openspec/specs/privacy-rules`](../openspec/specs/privacy-rules/spec.md):

> Jeder Beitrag, der neuen Quellcode einführt, SHALL vor Merge
> `python3 scripts/utils/check_source_privacy.py` mit Exit-Code 0 bestehen.

Einige Prüfungen sind nicht Teil von `qa_check.py` und müssen separat laufen:

```bash
python3 scripts/check_all.py                    # Privacy + Anonymisierung + PII
python3 scripts/check_compliance.py             # Review-Warteschlange, s. compliance_baseline.json
python3 scripts/check_import_logging.py         # nur bei neuen/geänderten Importern
./tests/smoke.sh                                # Pipeline läuft durch
```

Lies vorher [`openspec/specs/`](../openspec/specs/) — dort stehen die Anforderungen,
auf die ein Review zeigt, u. a. keine hartkodierte IANA-Zeitzone, geräteagnostisches
Laden über eine Präferenzkette statt einer einzelnen `device_id`, zweisprachige
Ausgabe über `t()`, und Befund-Konfidenz über `modules/confidence.py` statt eigener
Vokabulare.

### Prüfung von `@refs`-Zitaten

Zwei getrennte Tools prüfen die in `@refs` eines Moduls angegebenen DOIs/PMC-IDs —
sie stellen unterschiedliche Fragen und laufen zu unterschiedlichen Zeitpunkten:

| | `tools/check_doi_resolves.py` | `tools/verify_refs.py` |
|---|---|---|
| Gestellte Frage | Existiert dieser Identifier **überhaupt**? | Verweist dieser Identifier auf **genau dieses Paper**? |
| Methode | Fragt Crossref ab, mit Fallback auf DataCite (die beiden DOI-Registrierungsstellen für Zeitschriftenartikel bzw. Datensätze/Software wie Zenodo-Records) | Lässt ein LLM (Perplexity) den Zitattext mit dem tatsächlich aufgelösten Inhalt vergleichen |
| Braucht API-Key | Nein | Ja (`llm.perplexity_api_key`) |
| Kosten | Kostenlos, kein Rate-Limit-Risiko | API-Kosten pro Zitat |
| Wann ausführen | Jederzeit — günstig genug für CI oder als Gewohnheit | Nur als Pre-Release-Gate; Zitate ändern sich selten |
| Ein sauberer Lauf bedeutet | Der Identifier ist nicht tot/verschrieben | Menschliche Prüfung trotzdem nötig — auch das Modell kann irren |

Zuerst `check_doi_resolves.py` laufen lassen: Ein DOI, der überhaupt nicht auflöst,
ist eine deutlich billiger zu erkennende Fehlerklasse als ein DOI, der auf das
*falsche* Paper verweist — und es gibt keinen Grund, API-Aufrufe für die
Verifikation eines Zitats auszugeben, dessen Identifier schon bekanntermaßen tot ist.

## Versionierung und Changelogs

Keine Daten oder Versionsnummern in Dateiinhalte (Docstrings, Kommentare,
Doku) hartcodieren, um festzuhalten *wann* etwas geändert wurde oder *welche*
Revision es eingeführt hat — z.B. "Fixed 2026-07-18", "Version 3.1", "Stand:
2026-07-22", eine Changelog-Tabelle mit Datumsspalte, oder ein datierter
Dateiname wie `plan_x_2026-07-14.md`.

Git trägt diese Information bereits: die Commit-Historie für das tägliche
"was wurde geändert und warum", und — sobald das Projekt eine stabile
Release-Historie hat — Tags/GitHub-Releases für "welche Version hat das
eingeführt". Dieselbe Information zusätzlich im Dateiinhalt zu verewigen
dupliziert sie nur an einer Stelle, die veraltet (niemand aktualisiert eine
Changelog-Tabelle, wenn der Fix später nochmal gefixt wird), und vor dem
Release bringt es gar nichts, weil die Commit-Historie, auf die implizit
verwiesen wird, ohnehin vor dem ersten öffentlichen Release gesquasht wird.

Beschreibe *was* geändert wurde und *warum*, nicht *wann* — das Datum
trägt die Commit-Nachricht oder der PR.

**Ausnahme:** Zitate externer Quellen — Versionen medizinischer Leitlinien
(z.B. "AWMF S3-Leitlinie, Version 6.0"), Publikationsjahre, DOIs — sind
fachlicher Inhalt, kein Projekt-Changelog, und bleiben.

---

## Persönliche Fallbeispiele

Keine echten persönlichen Gesundheitsereignisse als motivierendes Beispiel
oder Begründung in Docs, Kommentaren oder Docstrings erzählen — auch nicht
generalisiert oder anonymisiert ("bei einem dokumentierten Fall zeigte
sich...", "in einem Fall stellte sich heraus, dass..."). Dieses Repo
beschreibt die Pipeline und ihre Begründung generisch; die tatsächlichen
Gesundheitsdaten — inklusive Anekdoten darüber, was damit passiert ist —
bleiben lokal, im gitignorten `intern/`-Verzeichnis oder den privaten
Notizen der Person, niemals in getrackten Dateien.

Das unterscheidet sich von der Daten/Versionen-Regel oben: dafür gibt es
keinen mechanischen Check (anders als eine feste Liste verbotener
Bezeichner erfordert das Erkennen von "das ist eine echte persönliche
Anekdote, als generisches Beispiel getarnt" Einschätzung, kein
String-Matching). Vor einem "warum das wichtig ist"/motivierenden Absatz
fragen: *Ist das eine allgemeine Tatsache über das Thema, oder etwas
Konkretes, das mit den Daten einer bestimmten Person passiert ist?* Falls
Letzteres: generalisieren oder weglassen.

Dieselbe Einschätzung gilt für Verweise auf `intern/` aus getrackten
Dateien: als Architektur-Fakt darauf zu verweisen ("private Notizen liegen
lokal unter `intern/`, siehe die Backup-Doku") ist okay und wird an
anderer Stelle in diesem Repo so gemacht; auf eine *konkrete* private
Datei oder ein Backlog-Item aus unabhängigem Inhalt zu verweisen nicht —
das bringt einer externen Leserin nichts (sie kann es eh nicht öffnen)
und verrät nur, dass es private Notizen zu genau diesem Thema gibt.

---

## Neuen Importer hinzufügen

Eine Datei in `scripts/importers/import_<quelle>.py` anlegen und die Funktion `run()` implementieren:

```python
from modules.base import ImportResult, resolve_person, resolve_timezone, local_date

def run(conn, data_path, lang='de', person=None) -> ImportResult:
    result = ImportResult()
    # ...
    return result
```

### ImportResult

```python
from dataclasses import dataclass, field

@dataclass
class ImportResult:
    rows_inserted: int = 0
    rows_skipped:  int = 0
    errors:        list[str] = field(default_factory=list)
```

### Hilfsfunktionen

| Funktion | Zweck |
|---|---|
| `resolve_person(conn, device_id, device_user_id, explicit)` | Gibt `person_id`-String zurück — sucht Gerätebesitzer oder Waagen-Slot |
| `resolve_timezone(conn, ts_utc, person, device_id, session_id, embedded_offset)` | Gibt `ZoneInfo` zurück — 6-stufiger Fallback von GPS bis Heimat-Timezone |
| `local_date(ts_utc, tz)` | Gibt `YYYY-MM-DD` zurück für den lokalen Kalendertag |

### Duplikat-Behandlung

`INSERT OR IGNORE` für alle Inserts verwenden — der Primary Key verwirft exakte Duplikate lautlos:

```python
conn.execute("""
    INSERT OR IGNORE INTO measurements (ts, date, metric, value, unit, device_id, person)
    VALUES (?, ?, ?, ?, ?, ?, ?)
""", (ts, date, metric, value, unit, device_id, person))
result.rows_inserted += conn.execute("SELECT changes()").fetchone()[0]
```

### Personen-Auflösung

```python
person = resolve_person(conn,
    device_id=device_id,         # sucht in devices.person
    device_user_id=slot,         # sucht in persons.device_user_id (z.B. 'u1', 'u2')
    explicit=person_param)       # überschreibt alles, wenn angegeben
```

### Timezone-Auflösung

```python
tz = resolve_timezone(conn,
    ts_utc=ts_utc,
    person=person,
    device_id=device_id,         # versucht devices.timezone (Stufe 5)
    session_id=session_id,       # versucht session_tracks GPS (Stufe 1)
    embedded_offset='+02:00')    # Polar GDPR eingebetteter Offset (Stufe 3)
date = local_date(ts_utc, tz)
```

### Import protokollieren

```python
log_import(conn, "import_meinequelle", data_path, result.rows_inserted, result.rows_skipped,
          person=person)
```

`person` sollte derselbe aufgelöste Wert sein, der auch für die eigentlichen Schreibzugriffe oben verwendet wird — explizit übergeben, nicht auf den Standard verlassen. Falls eine Migration oder ein Importer tatsächlich personenübergreifend arbeitet statt für eine Person (selten — die meisten Importer schreiben die Daten einer Quelle für eine Person), `person=None` explizit übergeben statt das Argument wegzulassen: Weglassen fällt auf die konfigurierte `OWN_PERSON_ID` zurück, was eine personenübergreifende Operation fälschlich einer einzelnen Person zuordnen würde. `git_commit` wird automatisch erfasst, kein Parameter nötig.

### In import_all.py registrieren

Eine Zeile in `scripts/import_all.py` ergänzen:

```python
from importers import import_meinequelle
results['meinequelle'] = import_meinequelle.run(conn, cfg['meinequelle_path'], person=args.person)
```

### Analyse-Skripte bekommen Logging automatisch

Anders als Importer müssen `analyse_*.py`-Skripte selbst nichts aufrufen, um protokolliert zu werden — jeder über `analyse_all.py` laufende Skript-Durchlauf wird automatisch in `analysis_log` erfasst (Skript, Git-Commit, Exit-Code, Dauer). Beim Schreiben eines neuen Analyse-Skripts ist nichts zu ergänzen.

---

## Neues Export-Profil hinzufügen

Eine JSON-Datei in `scripts/exporters/profiles/<profilname>.json` anlegen:

```json
{
  "name": "cardiology",
  "description": "Datenpaket für Kardiologen: HR, HRV, SpO2, AFib-Burden, EKGs, Blutdruck",
  "description_en": "Data package for cardiologists: HR, HRV, SpO2, AFib burden, ECG, blood pressure",
  "aliases": [],
  "queries": {
    "daily_heart": "SELECT date, person, resting_hr, hrv_rmssd_ms, spo2_avg FROM daily_summary WHERE person = :person AND date BETWEEN :date_from AND :date_to ORDER BY date",
    "ecg_sessions": "SELECT datetime, classification, symptoms, device_id FROM ecg_sessions WHERE person = :person AND date(datetime) BETWEEN :date_from AND :date_to ORDER BY datetime"
  }
}
```

- Jeder Eintrag in `queries` ist ein benanntes, vollständiges SQL-`SELECT`-Statement — der Name wird zum Ausgabedatei-/Sheet-Namen.
- Named Parameters `:person`, `:date_from`, `:date_to` werden automatisch aus den CLI-Flags injiziert. `--person all` ersetzt `person = :person` per Regex durch `1=1` — die Filterbedingung sollte daher als wörtlicher `person = :person`-Vergleich geschrieben werden, damit `all` funktioniert.
- Optionale `aliases`-Liste erlaubt, ein Profil unter weiteren Namen aufzurufen (z.B. ist `metabolic` auch als `diabetology`/`endocrinology` erreichbar).
- Optionales `algorithm_note` (String) dokumentiert nicht klinisch validierte Erkennungslogik in einer Query, wird beim Export mit angezeigt.

Kein Python nötig — `export_health.py` lädt alle Profile beim Start aus diesem Verzeichnis.

---

## Neues Gerät hinzufügen

Eine Zeile in die `devices`-Tabelle einfügen:

```sql
INSERT INTO devices (device_id, brand, model, serial, sensor_type, person, date_from, date_to, timezone)
VALUES ('polar_h10_3', 'Polar', 'H10', 'XXXXXXXX', 'chest_strap', 'self', '2026-06-01', NULL, NULL);
```

`sensor_type`-Werte:

| Wert | Beschreibung |
|---|---|
| `optical_wrist_gps` | Optischer Handgelenks-Sensor mit eingebautem GPS |
| `optical_wrist` | Optischer Handgelenks-Sensor ohne GPS |
| `chest_strap` | Brustgurt (Beat-to-beat RR) |
| `ring` | Smart Ring (optisch, Finger) |
| `handheld_gps` | Handheld-GPS-Gerät |
| `scale` | Körperzusammensetzungs-Waage (Bioimpedanz) |
| `bp_monitor` | Blutdruckmessgerät (oszillometrisch) |
| `glucometer` | Blutzuckermessgerät (kapillär, manuell) |
| `thermometer` | Thermometer (klinisch) |
| `smartphone` | Smartphone (GPS-Quelle, HA Companion) |
| `cgm` | Kontinuierliches Glukose-Messgerät |
| `hub` | Smart-Home-Hub (z.B. Home Assistant) |
| `weather_station` | Lokale Wetterstation (z.B. EcoWitt) |

Für geteilte Geräte (Waage, Blutdruckmessgerät, Thermometer) `person = NULL` setzen und `device_user_id` in der `persons`-Tabelle für die Slot-Zuordnung nutzen.

---

## Neue Metrik hinzufügen

Die `measurements`-Tabelle ist EAV — keine Schema-Änderung nötig. Einfach Zeilen einfügen:

```sql
INSERT OR IGNORE INTO measurements (ts, date, metric, value, unit, device_id, person)
VALUES ('2026-06-01T07:00:00Z', '2026-06-01', 'meine_neue_metrik', 42.0, 'unit', 'mein_geraet', 'self');
```

Für kategorische Metriken (Text-Werte) `value_text` verwenden und `value` als `NULL` lassen:

```sql
INSERT OR IGNORE INTO measurements (ts, date, metric, value, value_text, device_id, person)
VALUES ('2026-06-01T07:00:00Z', '2026-06-01', 'resilience_level', NULL, 'strong', 'oura_4', 'self');
```

---

## Neue Person hinzufügen

Eine Zeile in `persons` einfügen:

```sql
INSERT INTO persons (person_id, display_name, device_user_id, timezone)
VALUES ('partner', NULL, 'u2', 'Europe/Berlin');
```

- `person_id` wird in allen Gesundheitsdaten-Tabellen verwendet (Spalte `person`).
- `display_name` ist optional — für klinischen Einsatz `NULL` lassen und einen anonymisierten Hash als `person_id` nutzen.
- `device_user_id` mappt Waagen-Slot-Kennungen (`u1`, `u2`) automatisch auf Personen.
- `timezone` ist die Heimat-Timezone als Fallback (IANA-Name, z.B. `Europe/Berlin`).

---

## Verzeichnisstruktur

```
scripts/
├── importers/
│   ├── import_polar.py         — Polar GDPR-Export
│   ├── import_apple.py         — Apple Health export.zip
│   ├── import_oura.py          — Oura API
│   ├── import_garmin.py        — Garmin Connect
│   ├── import_beurer.py        — Beurer Health Manager Pro
│   ├── import_omron.py         — Omron Connect
│   ├── import_ecowitt_csv.py   — EcoWitt Wetterstation
│   ├── import_homeassistant.py — Home Assistant
│   └── ...                     — eine Datei pro Quelle
├── compute/
│   └── compute_*.py            — Abgeleitete-Tabellen-Scripts, Reihenfolge über compute_all.py
├── analysis/
│   └── <fachgebiet>/analyse_*.py — Auswertungen und Berichte, ein Unterordner pro Fachgebiet
├── exporters/
│   └── profiles/
│       ├── cardiology.json
│       ├── sleep.json
│       └── ...                 — eine JSON-Datei pro Profil
├── modules/
│   ├── base.py                 — ImportResult, resolve_person(), resolve_timezone(), local_date()
│   ├── i18n.py                 — zweisprachiger Helfer: t("DE-Text", "EN-Text")
│   └── db.py                   — open_db() / open_medicine_db() Connection-Helfer
├── utils/
│   └── create_schema.py        — Schema-Definition (Single Source of Truth)
├── export_health.py             — Haupt-Export-Runner
├── import_all.py                — Führt alle Importer aus
└── compute_all.py               — Führt compute/-Scripts in Abhängigkeitsreihenfolge aus
```
