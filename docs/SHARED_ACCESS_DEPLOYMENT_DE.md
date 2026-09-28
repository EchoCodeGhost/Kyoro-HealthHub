# Geteilter Zugriff — Bereitstellung und Verwaltung

> **English version:** [SHARED_ACCESS_DEPLOYMENT.md](SHARED_ACCESS_DEPLOYMENT.md)

**Fokus-Hinweis:** Kyoro-HealthHub ist bewusst auf **Privatnutzung** fokussiert — Einzelpersonen, Familien und Freundeskreise, die ihre eigenen Gesundheitsdaten verwalten. Das ist eine regulatorische Entscheidung, keine bloße Beschreibung: professioneller/institutioneller Einsatz (eine Arztpraxis, die Patient:innen behandelt, eine formale Forschungsstudie) löst völlig andere Pflichten aus (z. B. nach dem EU AI Act und Medizinprodukterecht), die dieses Projekt nicht verfolgt und nicht zu erfüllen behauptet. Der unten beschriebene Isolierte-Instanzen-plus-Berechtigungs-Broker-Mechanismus existiert, weil **starke Zugriffskontrolle auch ein Privatnutzungs-Feature ist** — z. B. wenn ein Familienmitglied besonderen Schutz für sensible Daten möchte, oder eine vertraute Person mit expliziter, widerrufbarer Erlaubnis hilft, die Daten einer/eines Angehörigen zu verwalten — nicht weil das Projekt institutionellen Einsatz anstrebt. Wer diesen Mechanismus trotzdem in einem professionellen/institutionellen Kontext nutzt, trägt die eigene Verantwortung, das gegen geltendes Recht zu prüfen — dieses Projekt strebt dafür keine Zertifizierung an.  
**Verantwortlich:** Siehe den lokalen Plan für geteilten Mehrpersonen-Zugriff (nicht Teil dieses Repos).

---

## Übersicht

Kyoro-HealthHub ist für den **gleichrangigen Betrieb in drei privaten Kontexten** gebaut:

| Kontext | Isolationsebene | Berechtigung | Standard-Zugriff |
|---------|----------------|--------------|------------------|
| Einzelnutzer:in | Eine `health.db` pro Person | Keine (lokal) | Volle Kontrolle |
| Familie/Freunde (einfach) | Eine `health.db` pro Person | Keine (lokal, vertrauensbasiert) | Volle Kontrolle |
| Familie/Freunde (zugriffskontrolliert) | **Isolierte Instanzen** pro Person | **Broker-gesteuert** (Spur B) | Kein Zugriff (Default-Deny) |

> **Hinweis:** Die zugriffskontrollierte Variante nutzt dasselbe Sicherheitsmodell, unabhängig davon, wer innerhalb eines Haushalts oder Freundeskreises konkret Zugriff gewährt/erhält — keine Abstriche je nach Beziehung.

---

## Nebenläufigkeit verstehen: Warum es zwei Zugriffswege gibt

**Diese Frage kommt als Erstes auf, sobald das für mehr als eine Person
eingerichtet wird, deshalb steht sie hier ganz am Anfang, ausführlich und
mit konkretem Alltagsbeispiel — nicht nur als technische Randnotiz.**

Kyoro-HealthHub hat **zwei völlig unabhängige Zugriffswege** auf die Daten
einer Person — nicht weil das kompliziert sein soll, sondern weil es zwei
grundverschiedene Tätigkeiten abbildet, die tatsächlich zu
unterschiedlichen Zeiten und auf unterschiedliche Weise passieren:

| | **Weg 1: CLI-Skripte** (Import, Compute, Analyse) | **Weg 2: Kyoro SymptomTrack-Web-App** (Symptom-Tracking) |
|---|---|---|
| Wer nutzt das? | Wer auch immer die Daten verwaltet, meist einmalig/periodisch pro Person | Die Personen selbst + wer ihnen hilft, laufend, den ganzen Tag |
| Wie läuft ein Vorgang ab? | Ein Terminal-Befehl, der einige Sekunden bis Minuten läuft, dann fertig ist | Viele kurze Anfragen (Klicks/Eingaben) über den Tag verteilt, an einen dauerhaft laufenden Server |
| Wie viele Personen gleichzeitig **in einem Prozess**? | Eine — für die Dauer des einen Befehls | Viele — der Server bedient zur selben Sekunde mehrere Personen |
| Zugriffsmechanismus | Umgebungsvariable `KYORO_ACTIVE_PATIENT_DIR` (pro Terminal-Fenster/Prozess) | Expliziter Parameter `patient_pseudo` in jeder einzelnen Anfrage + Berechtigungsprüfung |
| Warum dieser Mechanismus? | Betrifft nur den einen laufenden Prozess — kein Umbau der 385 bestehenden Skripte nötig | Ein Server-Prozess bedient viele Menschen gleichzeitig — eine globale Variable würde zwischen ihnen "durchsickern" |

### Ein konkreter Haushalts-Morgen

**8:00 Uhr — Anna trägt auf ihrem eigenen Handy Symptome in die
Kyoro SymptomTrack-App ein.**

Ihr Handy spricht über das Internet mit **einem einzigen, durchgehend
laufenden Server** (der Kyoro SymptomTrack-Backend-Prozess). Dieser Server läuft rund
um die Uhr und bedient in diesem Moment vielleicht mehrere Personen
gleichzeitig, die parallel an ihren Handys tippen. Jede einzelne Anfrage
von Annas Handy sagt dem Server dabei explizit, wer sie ist
(`patient_pseudo=PT-XXXX`) — so wie beim Online-Banking jede Anfrage die
Konto-ID mitschickt. Der Server prüft bei **jeder einzelnen Anfrage** neu:
ist diese Person für diese Daten berechtigt? Deshalb **muss** hier ein
Parameter pro Anfrage mitgeschickt werden — eine globale Einstellung
"aktuell ist Anna dran" würde nicht funktionieren, weil im selben
Moment auch Ben über sein Handy mit demselben Server spricht.

**8:05 Uhr — gleichzeitig öffnet Sam (hilft beim Verwalten der
Haushaltsdaten) ein Terminal-Fenster, um Bens Fitness-Tracker-Daten zu
importieren** (das macht Sam z. B. einmal wöchentlich pro Person mit
Wearable).

```bash
export KYORO_ACTIVE_PATIENT_DIR=~/.config/kyoro-master/patients/PT-BEN/
python3 scripts/import_all.py       # läuft z.B. 10 Minuten
python3 scripts/compute_all.py      # läuft danach ebenfalls einige Minuten
```

Das ist ein **komplett separater Vorgang**, unabhängig vom laufenden
Web-Server. Für die Dauer dieses einen Terminal-Fensters ist
"Ben" eingestellt — aber das betrifft **ausschließlich dieses eine
Fenster**, nicht den ganzen Haushalt und nicht den Web-Server, der parallel
weiterläuft und Annas Handy-Eingaben bedient.

### "Aber Import/Compute dauern doch eine Weile — blockiert das nicht alles andere?"

**Nein.** Die Umgebungsvariable `KYORO_ACTIVE_PATIENT_DIR` gilt **nur für
den einen Prozess, in dem sie gesetzt wurde** — sie "strahlt" nicht auf
andere Terminal-Fenster, andere Nutzer:innen oder den Web-Server ab. Das
ist elementares Betriebssystem-Verhalten: Umgebungsvariablen werden beim
Start eines Prozesses von seinem Elternprozess (dem Terminal) übernommen
und sind danach isoliert — zwei parallel laufende Terminal-Fenster haben
unabhängige Kopien.

**Konkret:** Sam öffnet **ein zweites Terminal-Fenster** und importiert
**gleichzeitig** Annas Daten:

```bash
# Terminal-Fenster 1 (läuft bereits seit 8:05 Uhr)
export KYORO_ACTIVE_PATIENT_DIR=~/.config/kyoro-master/patients/PT-BEN/
python3 scripts/import_all.py       # noch am Laufen

# Terminal-Fenster 2 (neu geöffnet, 8:07 Uhr)
export KYORO_ACTIVE_PATIENT_DIR=~/.config/kyoro-master/patients/PT-ANNA/
python3 scripts/import_all.py       # läuft PARALLEL zu Fenster 1, ohne Konflikt
```

Das funktioniert **völlig problemlos parallel**, aus zwei Gründen:

1. **Getrennte Prozesse, getrennte Umgebungsvariablen.** Fenster 1 "weiß"
   nichts von Fenster 2s Einstellung und umgekehrt.
2. **Getrennte Dateien.** Bens Daten liegen in
   `PT-BEN/data/health.db`, Annas in
   `PT-ANNA/data/health.db` — zwei komplett unabhängige SQLite-Dateien.
   Das eine Skript schreibt in Datei A, das andere in Datei B. Es gibt
   **keinen gemeinsamen Ort**, an dem sie sich in die Quere kommen
   könnten.

**Die einzige echte Einschränkung:** *Innerhalb eines einzigen*
Terminal-Fensters/Prozesses kann nicht gleichzeitig "Ben" und
"Anna" eingestellt sein — ein laufender `import_all.py`-Prozess ist
für die Dauer seines Laufs auf eine Person festgelegt. Das ist aber
keine neue Einschränkung durch das Mehrpersonen-Modell: Ein einzelner
Prozess konnte ohnehin immer nur einen Import nach dem anderen
sequenziell abarbeiten, unabhängig davon, ob es um eine oder viele
Personen geht.

**Realistisches Bild für einen Haushalt mit mehreren Personen:** Es gibt
**keinen künstlichen Flaschenhals im Design**, der erzwingt "immer nur
eine Person nach der anderen". Es können so viele parallele
Terminal-Fenster/Prozesse geöffnet werden, wie der Rechner an
Rechenleistung und Ein-/Ausgabe-Kapazität hergibt — die Grenze ist reine
Hardware-Kapazität, nicht die Architektur. Der einzige Fall, der
tatsächlich serialisiert (nacheinander statt gleichzeitig abläuft), wäre:
**derselbe** Personen-Import wird versehentlich zweimal gleichzeitig
gestartet — dann greift die normale SQLite-Sperrlogik (WAL-Modus,
`busy_timeout`) auf **dieser einen** Datei, genau wie im
Einzelnutzer:innen-Betrieb heute auch schon.

### Warum der Web-Server (Kyoro SymptomTrack) das anders lösen muss

Der Web-Server ist ein **einziger, dauerhaft laufender Prozess**, der
über den Tag verteilt Anfragen von vielen verschiedenen Personen
gleichzeitig beantwortet — im Unterschied zu den
CLI-Skripten, die nur kurz laufen und dann beendet sind. Eine
Umgebungsvariable "aktuell ist Person X dran" würde in diesem einen
Prozess für **alle gleichzeitigen Anfragen** gelten — Annas Anfrage
und Bens Anfrage kämen im selben Sekundenbruchteil beim selben
Serverprozess an, und eine globale Variable könnte nicht für beide
gleichzeitig unterschiedliche Werte haben. Deshalb bekommt dort **jede
einzelne Anfrage** ihren eigenen, expliziten `patient_pseudo`-Parameter
mitgegeben (siehe Abschnitt "Beispiel: Zugriff prüfen" unten), und der
Berechtigungs-Broker (`authz.check_patient_access()`) prüft bei jeder
Anfrage neu, ob die anfragende Person für genau diese Daten berechtigt
ist.

**Kurzformel:** Ein Prozess pro Sitzung (CLI, batchartig) → Umgebungsvariable
reicht, spart den Umbau von 385 bestehenden Skripten, und mehrere
Personen können trotzdem parallel an verschiedenen Daten
arbeiten, weil jedes Terminal-Fenster sein eigener, unabhängiger Prozess
ist. Viele gleichzeitige Anfragen in einem einzigen laufenden Prozess
(Web-Backend) → Parameter pro Anfrage ist zwingend nötig, sonst würden sich
die Daten verschiedener Personen im selben Prozess vermischen.

---

## Architektur: Zwei Spuren

### Spur A — Instanz-Isolation (Basis)

Jede Person bekommt ein **eigenes Verzeichnis** mit:

```
~/.config/kyoro-master/patients/
├── PT-A1B2C3D4/          # patient_pseudo (SHA-256 Hash aus person_number + group_id)
│   ├── .config/kyoro/
│   │   ├── health_config.json  # personenspezifische Config
│   │   └── identity.db         # lokale Identitätsabbildung (leer, da pseudo)
│   └── data/
│       ├── health.db           # verschlüsselte Gesundheitsdaten (Wearables/Sensoren)
│       ├── medicine.db         # verschlüsselte klinische Werte (Labor, Medikamente, Assessments)
│       └── db.key              # Verschlüsselungsschlüssel
└── PT-E5F6G7H8/
    └── ...
```

`medicine.db` (klinische Werte, die ein Arzt misst oder anordnet — Laborwerte,
Medikamente, Assessments; siehe [ARCHITECTURE_DE.md](ARCHITECTURE_DE.md)) wird
genauso pro Instanz isoliert wie `health.db`: `templates/health_config.example.json`
enthält einen `paths.medicine_db`-Eintrag, der Pfad-Rewrite-Schritt in
`onboard.py` schreibt ihn auf das Instanzverzeichnis um, und `onboard.py` führt
`create_medicine_schema.py` zusammen mit `init_db.py` aus, sodass das Schema
existiert, bevor ein klinischer Importer (`import_lab_csv.py`,
`import_saliva_ph.py`, `import_urine_strip.py`,
`import_genetics_aniva.py --mode biomarker`) gegen die Instanz läuft.

**Verwaltung:** `scripts/utils/manage/shared_access/manage_people.py`

| Befehl | Beschreibung |
|--------|--------------|
| `python3 scripts/utils/manage/shared_access/manage_people.py add "NUMMER" --group-id "Gruppen-ID"` | Legt neues Instanzverzeichnis an |
| `python3 scripts/utils/manage/shared_access/manage_people.py list` | Zeigt alle Personen |
| `python3 scripts/utils/manage/shared_access/manage_people.py activate PT-A1B2C3D4` | Gibt Export-Befehl für Shell aus |
| `python3 scripts/utils/manage/shared_access/manage_people.py deactivate PT-A1B2C3D4` | Markiert als inaktiv (kein Löschen) |

**Aktivierung für Skripte:**

```bash
# Shell-Session für eine bestimmte Person
export KYORO_ACTIVE_PATIENT_DIR="$HOME/.config/kyoro-master/patients/PT-A1B2C3D4"

# Alle Health-Skripte nutzen jetzt automatisch diesen Pfad
python3 scripts/import_polar.py
python3 scripts/analyse_hrv.py
```

> **Hinweis:** Die Skripte selbst müssen **nicht** geändert werden. Die Umleitung erfolgt über `KYORO_ACTIVE_PATIENT_DIR` in `scripts/health_config.py`.

---

### Spur B — Berechtigungs-Broker (Kyoro SymptomTrack Backend)

**Hinweis:** Spur B ist umgesetzt, aber — gemäß dem Fokus-Hinweis oben — dieser Abschnitt dokumentiert das gebaute Design für privaten, zugriffskontrollierten Mehrpersonen-Betrieb, keine Zertifizierung für institutionellen Einsatz.

Der Broker ist in **Kyoro SymptomTrack (PWA Backend)** implementiert und nutzt:

1. **`patient_assignments` Tabelle** (`pwa/backend/db.py`):
   - `user_id` (die Person, der Zugriff gewährt wird)
   - `patient_pseudo` (wessen Daten)
   - `role` (`owner` | `staff_readonly` | `staff_readwrite` | `admin`)
   - `granted_at`, `granted_by`, `revoked_at`

2. **`access_log` Tabelle** (Audit-Trail):
   - Jeder Zugriff (erlaubt oder verweigert) wird geloggt
   - Felder: `user_id`, `patient_pseudo`, `action` (`read` | `write` | `denied`), `ts`, `detail`

**Default-Deny:** Ohne Eintrag in `patient_assignments` → **403 Forbidden**.

---

## Berechtigungsmodell

### Rollen

| Rolle | Beschreibung | Schreibzugriff |
|-------|--------------|----------------|
| `owner` | Die Person selbst | ✅ |
| `staff_readwrite` | Eine vertraute Person mit Schreibrechten (hilft z. B. bei der Datenverwaltung) | ✅ |
| `staff_readonly` | Eine vertraute Person nur mit Lesezugriff | ❌ |
| `admin` | Administrator (braucht trotzdem expliziten Assignment-Eintrag) | ✅ |

> **Wichtig:** Auch `admin` braucht einen **expliziten Eintrag** pro Person. Es gibt keine globale "Super-Admin"-Rolle. Die Rollennamen (`staff_readwrite`/`staff_readonly`) sind unveränderte interne Bezeichner — sie gelten für jede vertraute Person, die beim Verwalten von Daten hilft, nicht speziell für professionelles Personal.

### Beispiel: Zuweisung erstellen

```sql
-- Anna (user_id = 'anna') darf ihre eigenen Daten PT-A1B2C3D4 lesen und schreiben
INSERT INTO patient_assignments 
  (user_id, patient_pseudo, role, granted_by, granted_at)
VALUES 
  ('anna', 'PT-A1B2C3D4', 'owner', 'admin', datetime('now'));

-- Sam (user_id = 'sam') darf nur mitlesen, um im Blick zu behalten
INSERT INTO patient_assignments 
  (user_id, patient_pseudo, role, granted_by, granted_at)
VALUES 
  ('sam', 'PT-A1B2C3D4', 'staff_readonly', 'anna', datetime('now'));
```

### Beispiel: Zugriff prüfen (im Code)

```python
# In FastAPI-Routen (pwa/backend/main.py)
from authz import check_patient_access

@app.get("/api/migraine/history")
def migraine_history(patient_pseudo: str, date_from: str, date_to: str,
                     user: CurrentUser):
    check_patient_access(user, patient_pseudo)  # 403 wenn nicht berechtigt
    return db.get_migraine_history(patient_pseudo, date_from, date_to)

# Oder als FastAPI-Dependency
from authz import require_patient_access

@app.get("/api/entries")
def get_entries(patient_pseudo: str,
               user: Annotated[CurrentUser, Depends(require_patient_access(patient_pseudo))]):
    return db.get_entries_for_range(patient_pseudo, ...)
```

---

## Tool-Integration: "Gegatet über Instanz-Auswahl"

**Prinzip:** Tools wie Datasette, Grafana oder Kyoro SymptomTrack selbst **prüfen keine Berechtigungen**. Stattdessen:

1. Der **Broker** entscheidet, welche Instanz eine Person öffnen darf
2. Ist die Instanz einmal freigegeben, dürfen Tools innerhalb dieser Instanz **frei arbeiten**
3. Die Beschränkung erfolgt durch **Instanz-Isolation**, nicht durch Tool-spezifische ACLs

### Datasette

```bash
export KYORO_ACTIVE_PATIENT_DIR="$HOME/.config/kyoro-master/patients/PT-A1B2C3D4"
python3 scripts/utils/serve_instance_tools.py datasette --port 8001
```

### Grafana

Wird von diesem Projekt nicht integriert. Wer Dashboards jenseits von
Datasette möchte, kann Grafana selbst gegen eine entschlüsselte Kopie der
Instanz-`health.db` einrichten — installationsabhängig, kein Teil dieses
Repos. Das gleiche Gating-Prinzip von oben gilt trotzdem: Auf welche
Instanz-DB Grafana zeigt, ist die einzige Datenquelle, die es sieht.

### Kyoro SymptomTrack (PWA)

Kyoro SymptomTrack nutzt bereits das Backend-Berechtigungssystem. Die Frontend-Routen sind an die Autorisierungs-Checks in `pwa/backend/authz.py` gebunden.

---

## Datenschutz & Security by Design

### 1. Anonymisierung/Pseudonymisierung

- **`identity.db`** (in `~/.config/kyoro/`) hält die einzige Abbildung zwischen Klartext-IDs und Pseudonymen
- **`health.db`** enthält **nur Pseudonyme** (`person`, `patient_pseudo`)
- **`patient_number_map`** in `master.db` (`~/.config/kyoro-master/master.db`) speichert Personennummern als **interne Aktenzeichen**, nicht als Klarnamen

**Beispiel:**
```python
# In scripts/utils/manage/shared_access/manage_people.py
def _pseudo(person_number: str, group_id: str = "") -> str:
    h = hashlib.sha256((person_number + group_id).encode()).hexdigest()
    return "PT-" + h[:8].upper()
```

### 2. Security by Default

- Neue Personen-Instanz: **standardmäßig isoliert + verschlüsselt**
- Neue vertraute Person: **standardmäßig kein Zugriff** (Default-Deny)
- Alle Daten: **verschlüsselt in health.db und medicine.db** (SQLCipher)

### 3. Audit-Trail

Jeder Zugriffsversuch wird in `access_log` geloggt:

```sql
SELECT * FROM access_log WHERE patient_pseudo = 'PT-A1B2C3D4';
-- action: 'read' | 'write' | 'denied'
-- detail: z.B. 'no assignment' oder 'readonly role, write attempted'
```

---

## Einrichtung: Schritt-für-Schritt

### 1. Voraussetzungen

- [ ] `pwa/` zurück nach `main` gemergt (erledigt)
- [ ] `scripts/utils/create_identity_schema.py` läuft fehlerfrei
- [ ] `python3 scripts/utils/create_identity_schema.py` (erstellt/upgradet `identity.db`)

### 2. Spur A einrichten

```bash
# 1. Personenregistratur initialisieren
python3 scripts/utils/manage/shared_access/manage_people.py add "NR-001" --group-id "Haushalt-A"
# → Legt ~/.config/kyoro-master/patients/PT-XXXXXXXX/ an

# 2. Personen-Onboarding (von überall ausführbar — onboard.py richtet sich
#    nach der Env-Var, nicht nach dem Arbeitsverzeichnis; kein "cd" nötig)
export KYORO_ACTIVE_PATIENT_DIR="$HOME/.config/kyoro-master/patients/PT-XXXXXXXX"
python3 ~/Kyoro-HealthHub/onboard.py

# 3. weitere Personen hinzufügen
python3 scripts/utils/manage/shared_access/manage_people.py add "NR-002" --group-id "Haushalt-A"
```

### 3. Spur B einrichten (Kyoro SymptomTrack Backend)

```bash
# 1. Auth-System konfigurieren
cd pwa/backend
python3 auth.py --setup
# → JWT-Secret + ersten User anlegen
# → TOTP-QR-Code scannen (z.B. Google Authenticator, Aegis)

# 2. Weitere User hinzufügen
python3 auth.py --add-user anna --name "Anna"
python3 auth.py --add-user sam --name "Sam" --readonly

# 3. Personen zuweisen (SQL oder Admin-UI)
# Siehe Abschnitt "Beispiel: Zuweisung erstellen" oben

# 4. TOTP End-zu-Ende testen (erforderlich, bevor Spur B produktiv genutzt wird)
python3 auth.py --totp-now anna  # aktuellen Code anzeigen
# → In Authenticator-App eingeben
# → POST /auth/login mit user_id + totp_code
# → Token gegen echten Endpoint testen
```

### 4. Broker in Routen einbinden

```python
# In pwa/backend/main.py (Beispiel für migraine-Routen)
from authz import check_patient_access

@app.get("/api/migraine/history")
def migraine_history(patient_pseudo: str, date_from: str, date_to: str,
                     user: CurrentUser):
    check_patient_access(user, patient_pseudo)
    return db.get_migraine_history(user.user_id, patient_pseudo, date_from, date_to)
```

---

## Migration bestehender Installationen

### Vorhandene Einzelnutzer:in-Installationen

Keine Änderungen nötig. Die bestehende `health.db` in `~/Kyoro-HealthHub/data/` bleibt funktionieren:

- `KYORO_ACTIVE_PATIENT_DIR` nicht gesetzt → Standardverhalten
- Alle Skripte arbeiten wie vorher

### Umstieg auf geteilten, zugriffskontrollierten Betrieb

1. **Backups erstellen:**
   ```bash
   cp -r ~/Kyoro-HealthHub/data ~/kyoro-backup/
   cp ~/.config/kyoro/health_config.json ~/kyoro-backup/
   ```

2. **Erste Person als Basis nehmen:**
   ```bash
   mkdir -p ~/.config/kyoro-master/patients/PT-BASE
   cp -r ~/Kyoro-HealthHub/data ~/.config/kyoro-master/patients/PT-BASE/
   cp ~/.config/kyoro/health_config.json ~/.config/kyoro-master/patients/PT-BASE/.config/kyoro/
   ```

3. **Person registrieren:**
   ```bash
   python3 scripts/utils/manage/shared_access/manage_people.py add "NR-001" --group-id "Haushalt-A"
   # → Legt PT-XXXXXXXX an
   ```

4. **Daten migrieren:**
   ```bash
   cd ~/.config/kyoro-master/patients/PT-XXXXXXXX/
   rm -rf data/ .config/kyoro/health_config.json
   cp -r ~/kyoro-backup/data .
   cp ~/kyoro-backup/health_config.json .config/kyoro/
   ```

---

## Gebündelter anonymisierter Export (mehrere Personen auf einmal)

Über den Export einer einzelnen Person hinaus führt
`scripts/exporters/export_research_cohort.py` das bestehende
`research`-Exportprofil über **alle aktiven, freigegebenen**
Instanzen zu einem anonymisierten Gesamtdatensatz zusammen. Das ist ein
allgemeines Werkzeug, um Daten mehrerer Personen zu einem
de-identifizierten Datensatz zusammenzuführen — nutzbar für jeden
privaten Zweck (z. B. anonymisierte Trends innerhalb einer Familie
vergleichen), nicht ausschließlich für formale Forschung. Die
vollständigen Anforderungen stehen in
`openspec/specs/research-cohort-export/spec.md`.

### 1. Freigabe erfassen, bevor exportiert wird

Der Export verweigert die Aufnahme jeder Instanz ohne aktive
(nicht widerrufene) Freigabe für den angeforderten Scope — kein
stilles Auslassen, harter Abbruch mit Liste der fehlenden Freigaben:

```bash
python3 scripts/utils/manage/shared_access/manage_access_grants.py grant \
    --person PT-A1B2C3D4 --scope export-2026-hrv-vergleich
python3 scripts/utils/manage/shared_access/manage_access_grants.py list --person PT-A1B2C3D4
python3 scripts/utils/manage/shared_access/manage_access_grants.py revoke \
    --person PT-A1B2C3D4 --scope export-2026-hrv-vergleich
```

Ein Widerruf löscht die Freigabezeile nicht (bleibt für die
Audit-Historie erhalten) — eine Person kann danach für denselben
Scope erneut freigeben; das CLI legt dafür eine neue Zeile an statt
die widerrufene wiederzuverwenden.

### 2. Export ausführen

```bash
python3 scripts/exporters/export_research_cohort.py \
    --scope export-2026-hrv-vergleich \
    --profile research \
    --quasi-identifiers age_band,timezone \
    --k 5 --age-band-width 5 \
    --date-from 2020-01-01 --date-to 2026-12-31
```

Fehlt einer aktiven Instanz die Freigabe für den Scope, bricht das
Tool **vor jeglichem Schreiben** ab und listet die fehlenden
Personen. Schlägt der Export-Subprozess einer Instanz fehl (z. B.
gesperrte oder beschädigte Datenbank), bricht der gesamte Lauf ab, statt
still einen unvollständigen Datensatz auszuliefern — die stderr-Ausgabe
zeigt, welche Instanz betroffen war.

### 3. Was wie anonymisiert wird

- **Datumsverschiebung**: jeder Datums-/Zeitstempel-Wert wird um einen
  Offset verschoben, der pro Person deterministisch ist (dieselbe
  Person → derselbe Offset bei jedem Lauf), aber aus der Ausgabe nicht
  rekonstruierbar. Spaltennamen werden über eine breite Heuristik erkannt
  (`_at`, `_date`, `_start`, `_end`, `_from`, `_to`, `_dt`, sowie
  `ts`/`date`/`datetime`/`timestamp`/`day`) **und** zusätzlich über den
  Wert selbst (alles, was wie ein ISO-8601-Datum aussieht, wird
  verschoben, auch wenn der Spaltenname nicht vorgesehen war) — diese
  doppelte Absicherung ist wichtig, weil ein einziges unverschobenes
  echtes Datum neben einem verschobenen es erlauben würde, den
  Personen-Offset zurückzurechnen und jede andere Spalte zu
  entschlüsseln.
- **Altersbänderung**: Geburtsdaten (falls vorhanden) werden zu
  N-Jahres-Bändern (Standard 5) statt exakter Daten.
- **k-Anonymität**: Zeilen werden nach den mit `--quasi-identifiers`
  angegebenen Spalten gruppiert; jede Gruppe unterhalb von `--k` wird aus
  dem Liefer-Datensatz entfernt und stattdessen in ein lokal verbleibendes
  `suppressed/`-Verzeichnis geschrieben (nie ausgeliefert). Existiert
  keine der angeforderten Quasi-Identifikator-Spalten in einer Tabelle,
  gibt das Tool eine deutliche Warnung aus und trägt das in
  `manifest.json` ein — es täuscht NICHT vor, die Prüfung sei gelaufen.

### 4. Ausgabe lesen

```
KYORO_MASTER_DIR/research_exports/<datum>/
├── deliverable/        # das, was tatsächlich weitergegeben wird
│   ├── measurements.csv
│   └── ...
├── suppressed/         # k-Anonymität-Ausschlüsse — bleiben lokal, nie ausgeliefert
└── manifest.json        # k, Altersband-Breite, QI-Spalten, Instanzzahlen,
                          # unterdrückte Zeilen pro Tabelle, Warnungen zu
                          # fehlenden QI-Spalten (enthält bewusst KEINE
                          # Pro-Person-Datumsoffsets oder Pseudonyme —
                          # das würde deren Zweck zunichtemachen)
```

### 5. Bekannte Einschränkung

Die Datumsverschiebung entfernt bewusst die zeitliche Ausrichtung
zwischen Personen (jede Person hat einen unabhängigen Offset) — ein
Einsatzzweck, der wirklich wissen muss "haben sich alle HRV-Werte in
derselben Kalenderwoche gemeinsam verändert", kann die Ausgabe dieses
Tools nicht unverändert nutzen; das würde einen separaten, sorgfältiger
abgestimmten Exportweg erfordern.

---

## Compliance & Ethik

- **Kein Profiling** (siehe `docs/ETHICS.md`)
- **Keine Nutzung durch Versicherungen/Arbeitgeber**
- **Nur Privatnutzung** — siehe Fokus-Hinweis am Anfang dieses Dokuments
- **Gleiche Regeln für alle, die die zugriffskontrollierte Variante nutzen**
- **Privacy by Design & by Default** (siehe Leitprinzipien im lokalen Plan-Dokument)

---

## Fehlerbehebung

### "Kein Zugriff auf diese Person zugewiesen"

1. Prüfen, ob User existiert:
   ```bash
   python3 pwa/backend/auth.py --list
   ```

2. Prüfen, ob Assignment existiert:
   ```sql
   SELECT * FROM patient_assignments 
   WHERE user_id = '<user_id>' AND patient_pseudo = '<patient_pseudo>'
     AND revoked_at IS NULL;
   ```

3. Assignment erstellen (falls fehlend):
   ```sql
   INSERT INTO patient_assignments 
     (user_id, patient_pseudo, role, granted_by, granted_at)
   VALUES 
     ('<user_id>', '<patient_pseudo>', 'staff_readwrite', 'admin', datetime('now'));
   ```

### TOTP-Login schlägt fehl

1. Secret prüfen:
   ```bash
   python3 pwa/backend/auth.py --totp-now <user_id>
   ```

2. Authenticator-App: Zeit synchronisieren
3. Code innerhalb von 30 Sekunden eingeben (Validierungsfenster: ±1 Code)

---

## Glossar

| Begriff | Erklärung |
|---------|-----------|
| `patient_pseudo` | `PT-` + SHA-256(person_number + group_id)[0:8] (z.B. `PT-A1B2C3D4`) — interner Bezeichner unverändert aus früheren Versionen |
| `person_number` | Internes Aktenzeichen (z.B. `NR-001`), **kein Klarname** |
| `instance_dir` | Vollständiger Pfad zum Verzeichnis der Person (z.B. `/home/user/.config/kyoro-master/patients/PT-A1B2C3D4`) |
| `user_id` | Benutzerkennung (z.B. `anna`, `sam`) |
| Default-Deny | Kein Zugriff ohne explizite Zuweisung |
