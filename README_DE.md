# Kyoro-HealthHub

Eine umfassende persönliche Gesundheitsplattform: Integration von Wearables und Medizingeräten, forensisch belastbare Datenpipeline, Symptom-Tracking, klinische Analyse und KI-gestützte Abfragen. Privacy-first, Privacy by Design: Deine Daten bleiben unter deiner Kontrolle, anonymisiert und pseudonymisiert an der Quelle.

> **English version:** [README.md](README.md)

---

## Warum Kyoro existiert

Menschen mit komplexen, chronischen oder medizinisch ungeklärten Erkrankungen werden von Spezialisten behandelt, die jeweils ihren Ausschnitt sehen. Der Kardiologe sieht das Herz. Der Neurologe die Nerven. Oft setzt niemand das Mosaik zusammen.

Kyoro kann dabei unterstützen: Jahre von Wearable-Daten, Laborbefunden, Symptomen und klinischen Ereignissen werden zu einer einzigen longitudinalen Zeitachse verbunden — und machen Muster sichtbar, die über Jahre und über Fachgrenzen hinweg leicht unbemerkt bleiben.

Ein verwandtes strukturelles Problem: Einmal vergebene Diagnosen werden nicht immer erneut hinterfragt, auch wenn sich der Stand der Wissenschaft weiterentwickelt. Eine persistente, unveränderliche Zeitachse kann das erleichtern: die Vergangenheit lässt sich jederzeit mit neuen Augen lesen — von dir, von deiner Ärztin, oder von dir in zehn Jahren.

Dazu kommt ein schlicht ökonomisches Problem: Jahre — manchmal Jahrzehnte — an Daten über Fachgrenzen hinweg gründlich zu lesen, Quellen gegeneinander abzugleichen und widersprüchliche Einschätzungen gegeneinander abzuwägen, kostet Stunden. Diese Zeit wird nirgendwo abgerechnet oder budgetiert, weder stationär noch ambulant. Kyoro ersetzt keine ärztliche Beurteilung; es übernimmt das Lesen, das sonst nie stattgefunden hätte, damit die knappe Zeit der Ärztin fürs Entscheiden zur Verfügung steht statt fürs Suchen.

Und, ganz pragmatisch: "Führen Sie ein Tagebuch" ist Standard-Ärzteempfehlung bei fast jeder unklaren Beschwerde — Ernährung, Schlaf, Symptome nach Belastung, jeweils separat. Bei mehreren gleichzeitigen Baustellen bedeutet das schnell zehn verschiedene Hefte oder Apps für zehn verschiedene Symptomarten. Kyoro ist auch einfach die bequemere Lösung dafür: ein System statt zehn — und macht aus den einzelnen Datensilos, die durch unterschiedliche Apps und Geräte (z. B. Oura, Kyoro SymptomTrack) ohnehin schon entstehen, ein einheitliches Ganzes, statt sie getrennt nebeneinander stehen zu lassen.

**Vier Phasen:**
1. **Verstehen** — Forensik: was ist passiert, wann, warum
2. **Behandeln** — Treiber identifizieren, gemeinsam mit ärztlicher Begleitung angehen
3. **Optimieren** — modifizierbare Risikofaktoren aktiv steuern
4. **Longevity** — die eigenen Karten kennen, das Umfeld dazu gestalten

Die Daten sind da. Was fehlte, war ein System, das sie liest.

*Kyoro stellt keine Diagnosen. Es gibt Spezialisten eine Richtung, in die sie schauen könnten — und Menschen im Idealfall wieder mehr Lebensqualität zurück.*

---

> ## ⚠️ Kein Medizinprodukt
>
> Diese Software **diagnostiziert, behandelt, heilt oder verhindert keine Krankheiten**. Alle Ausgaben —
> einschließlich Arrhythmie-Erkennung, POTS-Kriterium, PEM-Korrelation, SpO₂-Belastung,
> HRV-Wendepunkte, ANS-Status, VLM-gestützte Bildanalyse (z. B. eines Muttermals oder
> Fundusfotos) und KI-generierter Text — sind heuristisch, basieren auf Verbrauchersensoren
> und dürfen **NICHT** für medizinische Entscheidungen verwendet werden.
>
> **Ergebnisse können in beide Richtungen falsch sein.** Ein falsch-positives Ergebnis kann
> auf etwas hinweisen, das gar nicht da ist; ein falsch-negatives kann etwas Reales übersehen.
> Weder diese Software noch eine ihrer KI-Komponenten ist ein Arzt — die Entscheidungshoheit
> liegt immer bei einer qualifizierten ärztlichen Fachperson, die vor jeder Handlung aufgrund
> einer Auswertung konsultiert werden muss.
>
> **Sei darauf vorbereitet, was du finden könntest — und darauf, Unsicherheit aushalten zu
> müssen.** Wenn ein VLM z. B. ein Muttermal als hochriskant einstuft, oder ein anderer
> beunruhigender Befund auftaucht, löst sich das nicht von selbst auf — das kann nur eine
> Ärztin oder ein Arzt. Du trägst die Konsequenzen dessen, wie du auf eine Auswertung
> reagierst oder nicht reagierst. Überlege dir vor einer Analyse, bei der du eine belastende
> Erkenntnis für möglich hältst, ob du diese Unsicherheit gerade aushalten kannst, und zieh
> bei Bedarf jemanden hinzu, dem du vertraust.
>
> **Die Überprüfung der zugrunde liegenden Literatur steht noch aus.** Wissenschaftliche
> Zitate im gesamten Code (siehe die "Evidence tier"-Kennzeichnungen in `docs/`) wurden ad
> hoc pro Skript ergänzt, nicht durch einen eigenen Prüfdurchgang. Genau dieser Review war
> die letzten Wochen der Hauptgrund, warum die Veröffentlichung nicht stattfand. Die
> Entscheidung war: lieber jetzt mit diesem offenen Punkt veröffentlichen, als noch länger
> zu warten — damit möglichst schnell möglichst viele Menschen von Kyoro profitieren können,
> auch mit noch teils ungenauen oder fehlerhaften Referenzangaben. Er steht auf der
> TODO-Liste des Projekts und wird als Nächstes angegangen. Behandle jedes Zitat bis dahin
> als ungeprüft.
>
> Vollständiger Haftungsausschluss: [NOTICE_DE](NOTICE_DE)

> ## 🔒 Deine Daten bleiben auf deiner Maschine
>
> Datenbank, Rohdaten-Exporte und Konfiguration liegen ausschließlich lokal auf deinem
> Dateisystem. Die Software führt keine Telemetrie und keine Hintergrund-Uploads durch.
> Externe Netzwerkzugriffe erfolgen nur für Hersteller-APIs, die du explizit konfigurierst
> (Garmin/Oura), und optionale Remote-KI-Anbieter (opt-in).
> Daten-Souveränität: [NOTICE_DE](NOTICE_DE)
>
> **Datenbankverschlüsselung:** Setze `db_key` in `~/.config/kyoro/health_config.json`, um
> AES-256-Verschlüsselung via SQLCipher zu aktivieren. Ohne diesen Schlüssel ist
> `data/health.db` eine unverschlüsselte SQLite-Datei, die jeder mit Dateisystemzugriff
> lesen kann.
>
> **Rohdaten und Backups:** Dateien in `imports/` werden von dieser Software nicht
> verschlüsselt. Schütze das Datenverzeichnis mit Festplatten- oder Ordner-Verschlüsselung
> (LUKS unter Linux, FileVault unter macOS, BitLocker unter Windows) — und wende dasselbe
> auf Backups an.
>
> **Externe KI-Anbieter:** Wenn du einen Remote-LLM verwendest (OpenRouter, Anthropic
> o. ä.), übertrage ausschließlich pseudonymisierte oder anonymisierte Daten — keine
> Rohdaten oder identifizierbaren Angaben. Bevorzuge Anbieter mit **Zero Data Retention
> (ZDR)**, die explizit garantieren, dass **übermittelte Daten nicht zum Modell-Training
> genutzt werden**, und stelle sicher, dass die Übertragung ausschließlich über
> verschlüsselte Verbindungen (TLS) erfolgt. API-Accounts und Zugangsdaten dürfen nicht
> zwischen Nutzern geteilt werden. Erwäge zusätzlich ein **VPN** für diesen
> Datenverkehr — es verbirgt deine IP-Adresse gegenüber dem Anbieter, als
> zusätzliche Schicht (nicht als Ersatz für Pseudonymisierung/ZDR oben).

---

## Was es kann

- **Alle Daten an einem Ort** — Wearables, Medizingeräte, Apps, Laborbefunde in einer Datenbank
- **Multi-Personen-Unterstützung** — gebaut für Privatnutzung: Einzelpersonen, Familien und Freundeskreise. Haushalt/Familie ist voll unterstützt. Isolierte Pro-Person-Instanzen plus Berechtigungs-Broker für stärkere Zugriffskontrolle sind gebaut (siehe [ARCHITECTURE_DE.md](docs/ARCHITECTURE_DE.md) und [SHARED_ACCESS_DEPLOYMENT_DE.md](docs/SHARED_ACCESS_DEPLOYMENT_DE.md)) für alle, die diesen Grad an Trennung innerhalb eines Haushalts oder Freundeskreises möchten. Dieses Projekt ist bewusst auf Privatnutzung fokussiert und strebt keine Zertifizierung für institutionellen Einsatz (Klinik/Forschung) an — siehe "Release-Status" unten.
- **Geräteübergreifende HRV-Analyse** — RMSSD-Trends über Jahre, konsistente Metrik-Definitionen
- **Arrhythmie-Erkennung** — Episoden-Erkennung aus 24/7-HR-Daten, EKG-Import (jeder EKG-fähige Wearable, Brustgurt-RR via ECGLogger/Kubios)
- **AF Evidence Score (AFES)** — täglicher 0–100 Multi-Signal-Risikowert für Vorhofflimmern aus 21 Kanälen; DFA alpha1 auf Brustgurt-Beat-to-Beat-Daten → [docs/AFES_DE.md](docs/AFES_DE.md)
- **Autonome Dysregulation** — PPT, Orthostase-Tests, KubiosHRV-Integration
- **Klinische Kriterien** — POTS-Kriterium, PEM-Muster, ANS-Status algorithmisch berechnet
- **Laborbefunde** — PDF-OCR-Pipeline: Scan → Review-CSV → KI-Analyse
- **Medizinische Dokumente** — PDF/Scan-OCR mit lokalem VLM (Qwen2.5-VL via OpenVINO)
- **Migräne-Tracking** — Import aus Migräne-App (.mbu), HIT-6, MIDAS, PGIC
- **Zyklus & Symptome** — WomanLog Pro, Flo, Symptomtagebuch mit Tageswerten
- **Ernährung** — FDDB-Ernährungstagebuch
- **KI-Abfragen** — Natürlichsprachliche Fragen an die eigene Datenbank (lokal oder OpenRouter)
- **Report zur Weitergabe an den Arzt** — Plots und strukturierte Befunde aus Rohdaten
- **Arzt-Export-Profile** — thematische CSV/JSON-Exporte für viele Fachrichtungen
- **FHIR-R4-Export** — `--format fhir` erzeugt ein standardbasiertes Bundle (Observation/Condition/Patient) für die Interoperabilität mit anderen Systemen; siehe [docs/FHIR_EXPORT_DE.md](docs/FHIR_EXPORT_DE.md)
- **Privacy-Compliance** — `check_source_privacy.py` stellt sicher, dass keine Diagnose-Namen oder persönlichen Identifier im Quellcode stehen; Pre-Commit-Hook erzwingt dies automatisch

---

## Geplante Features

- **Geführtes Anamnese-Interview** (geplant, siehe [openspec/changes/add-guided-anamnesis-interview](openspec/changes/add-guided-anamnesis-interview)) — ein KI-gestütztes, lokales, mehrsitzungsfähiges Interview-Werkzeug, das Expositions-/Reise- und Familienanamnese durch offenes, assoziatives Nachfragen (statt eines starren Formulars) rekonstruiert und strukturierte, fortsetzbare Notizen für die Arztvorbereitung erzeugt. Code existiert bereits, ist aber auf einen späteren Release verschoben — nicht Teil dieses Releases.

---

## Release-Status — verschoben / keine Zertifizierung geplant

Folgende Bereiche werden in diesem Release so ausgeliefert wie sie sind (oder gar nicht) und unterliegen ausdrücklich **nicht** dem üblichen Qualitätsanspruch:

- **Zugriffskontrollierte Mehrpersonen-Nutzung** — das Isolierte-Instanzen-plus-Berechtigungs-Broker-Design in [SHARED_ACCESS_DEPLOYMENT_DE.md](docs/SHARED_ACCESS_DEPLOYMENT_DE.md) ist für den privaten Mehrpersonen-Fall gebaut (z. B. ein Familienmitglied möchte besonderen Schutz, oder eine vertraute Person hilft mit expliziter, widerrufbarer Erlaubnis). Einfache Einzel- und Familiennutzung (einzelne/geteilte lokale Datenbank, keine Zugriffskontroll-Schicht) ist davon nicht betroffen. Echtes Testen unter realen Bedingungen des verbleibenden Punkts (ein TOTP-QR-Code-Scan, gebündelt mit dem PWA-Testing unten) ist weiterhin nach dem Release geplant — das ist funktionale Verifikation, kein Zertifizierungsprozess.
- **Umfang: nur Privatnutzung — nicht für Forschung, Institutionen oder kommerziellen Einsatz.** Dieses Projekt ist bewusst auf eine Einzelperson oder einen privaten Haushalts-/Freundeskreis zugeschnitten, der die eigenen Daten verwaltet, und strebt keine Zertifizierung für den Einsatz durch ein Forschungsprojekt, eine Klinik/Praxis oder einen anderen institutionellen/kommerziellen Betreiber an. Das ist keine willkürliche Einschränkung, sondern folgt direkt aus dem EU-Regulierungsrahmen:
  - **EU AI Act:** Art. 2 nimmt natürliche Personen, die ein KI-System für eine rein persönliche, nicht-berufliche Tätigkeit nutzen, von praktisch allen Pflichten aus. Auf diese Ausnahme stützt sich dieses Projekt. Sie gilt **nicht** für eine Forschungseinrichtung, Klinik oder ein Unternehmen, das dieselbe Software einsetzt — für solche Betreiber müssten die KI-gestützten Analysefunktionen vermutlich gegen die Hochrisiko-Kriterien in Anhang III geprüft werden (klinische Entscheidungsunterstützung passt plausibel dazu), was ein Risikomanagementsystem, Daten-Governance mit Bias-Dokumentation, technische Dokumentation, Protokollierung, ein Konzept für menschliche Aufsicht, Nachweise zu Genauigkeit/Robustheit/Cybersicherheit, ein Konformitätsbewertungsverfahren, eine CE-Kennzeichnung und eine EU-Datenbank-Registrierung nach sich ziehen würde — nichts davon wurde hier durchlaufen.
  - **Medizinprodukterecht (MDR):** Software, die von einer Fachperson zur Unterstützung einer klinischen Entscheidung genutzt wird, gilt üblicherweise unabhängig vom AI Act als "Software als Medizinprodukt". Das würde eine Risikoklassifizierung (vermutlich Klasse IIa oder höher), eine Bewertung durch eine Benannte Stelle, eine klinische Bewertung, ein ISO-13485-Qualitätsmanagementsystem, eine eigene CE-Kennzeichnung und Marktüberwachung nach Inverkehrbringen bedeuten — auch das wurde hier nicht durchlaufen.
  - **DSGVO auf institutioneller Ebene:** Eine Person, die die eigenen Gesundheitsdaten unter der Haushaltsausnahme verarbeitet, ist rechtlich etwas anderes als eine Institution, die die besonderen Kategorien personenbezogener Daten (Art. 9) vieler Personen verarbeitet. Letzteres braucht eine dokumentierte Rechtsgrundlage, eine Datenschutz-Folgenabschätzung, Auftragsverarbeitungsverträge mit jedem genutzten LLM-Anbieter, ein Verarbeitungsverzeichnis und in der Regel einen benannten Datenschutzbeauftragten — nichts davon liefert dieses Projekt von Haus aus.

  Die Nutzung dieser Software in einem Forschungs-, institutionellen oder kommerziellen Kontext, ohne all das oben Genannte eigenständig zu erfüllen, geschieht auf eigenes Risiko und in eigener Verantwortung des jeweiligen Betreibers; dieses Projekt bietet dafür keine Unterstützung, Gewährleistung oder Zertifizierung, weder jetzt noch geplant.
  - **Was das konkret für alles bedeutet, was die lokale Maschine verlässt:** `export_health.py` (die Arzt-Export-Profile, CSV/JSON/FHIR) enthält **ausschließlich Rohdaten** — deine eigenen gemessenen Werte, strukturiert zur Übergabe. Es bettet nie KI-generierte Kommentare ein. Die KI-gestützte Analyse (`analyse_all.py --llm`, `health_query.py`) ist ein separates Feature nur zur eigenen Nutzung; jeder von ihr erzeugte Text bekommt automatisch den Standard-KI-Hinweis angehängt (`ai_label()` in `modules/llm.py`: *"KI-generiert von {model} am {datum} | Nicht für klinische Diagnose"*). Falls du eine KI-kommentierte Analyse trotzdem ausdruckst oder weitergibst, reist dieser Hinweis mit — das ist kein Versprechen, das du selbst einhalten musst, macht die Analyse aber auch nicht zu etwas, auf das sich eine Fachperson ohne eigenes Urteil verlassen könnte.
- **Mobile App** (`mobile/KyoroVitalGuard/`) — **experimentell, kann zerbrechen.** Über Code-Review hinaus ungetestet; wird so ausgeliefert wie sie ist, folgt in einem späteren Release. Nicht für etwas Zeitkritisches (z. B. einen Alarm) verlassen, bevor es tatsächlich getestet wurde.
- **PWA** (`pwa/`, `tools/KST-PWA/`) — **experimentell, kann zerbrechen.** Über Code-Review hinaus ungetestet; wird so ausgeliefert wie sie ist, folgt in einem späteren Release. Nicht für etwas Zeitkritisches verlassen, bevor es tatsächlich getestet wurde.
- **Geführtes Anamnese-Interview** — implementiert, aber auf einen späteren Release verschoben (s. o.). Über den allgemeinen "keine Zertifizierung geplant"-Hinweis hinaus: Dieses Modul ist **noch nicht rock-solid**. Es ist KI-gesteuert, daher können seine assoziativen Nachfragen und die daraus extrahierten strukturierten Befunde unvollständig sein, einen Hinweis übersehen, den ein Mensch aufgegriffen hätte, oder falsch verstehen, was du eigentlich gesagt hast. Das nötige Dogfooding unter echten Bedingungen — findet das Tool wirklich Hinweise, die eine sorgfältige manuelle Durchsicht nicht auch gefunden hätte, funktioniert das Erinnerungsanker-Prompting wie gedacht, bleibt es über eine lange Mehrfach-Sitzung hinweg konsequent in einer Sprache — ist noch nicht erfolgt (siehe `add-guided-anamnesis-interview` Tasks 6.3–6.5). Behandle alles, was es erzeugt, als Entwurf, den du selbst durchsehen musst, nicht als fertige Anamnese.
- **Wissenschaftliche Referenzen** (`@refs`-Felder in allen Skripten, ~250 Zitate; Geräte-Validierungsquellen aufgelistet in [docs/references/device_validation.md](docs/references/device_validation.md)) — ein früherer KI-gestützter Verifikationslauf (`tools/verify_refs.py`, Perplexity) deckte nur eine Handvoll Zitate mit bereits bekannt kaputten DOIs ab und kennzeichnet selbst ausdrücklich, dass er **menschliches Review braucht, bevor er als verlässlich gilt** — dieses menschliche Review ist für die vollständige Zitatliste noch nicht abgeschlossen. Der Release hatte Vorrang vor dem Abschluss dieses Reviews, damit das System Menschen schneller erreichen und helfen konnte. Ein paar falsche DOIs wurden auf diesem Weg bereits gefunden; behandle jedes Zitat als vorläufig, bis es einen menschlich geprüften Status trägt.
- **Klinische Leitlinien sind standardmäßig deutsch/europäisch, ohne Länder-/Regionserkennung.** Skripte, die Vorsorge-Alter, Diagnosekriterien oder Nachsorge-Intervalle referenzieren (z. B. Koloskopie-Startalter, Sepsis-/Borreliose-Diagnosekriterien), sind aktuell fest auf deutsche Quellen (AWMF-S3-Leitlinien, RKI-Empfehlungen) verdrahtet. Es gibt weder ein Config-Feld noch einen Erkennungsmechanismus für das Land der Nutzerin/des Nutzers, und keine Logik, ein anderes nationales Leitlinien-System (z. B. USPSTF) auszuwählen. Außerhalb Deutschlands/des DACH-Raums jede aus einer Leitlinie abgeleitete Schwelle oder Empfehlung als Ausgangspunkt behandeln, der gegen die eigenen nationalen Leitlinien zu prüfen ist — nicht als direkt anwendbar.

---

## Unterstützte Datenquellen

### Wearables
Polar (Handgelenk, Arm-Multi-Positions-Sensor, + Brustgurt) · Apple Watch / Health · Oura Ring · Garmin

### Medizingeräte
Omron (Blutdruck) · Withings (Blutdruck, EKG, Waage, Körperzusammensetzung) · Beurer (Waage, Glukose, Thermometer) · Freestyle Libre (CGM) · RENPHO (Maßband) · Wellue O2Ring (kontinuierliches SpO2/Puls)

### Apps & Tools
KubiosHRV · HRV4Training · ECG Logger · HRV Logger · Sleep Cycle · WomanLog Pro · Flo · FDDB · Migräne-App · Symptomtagebuch · Shotsy · Headspace · Freeletics · Gymondo · Strava · Komoot

### Kontext
Home Assistant (Umgebung, Anwesenheit, GPS) · EcoWitt (lokale Wetterstation)

→ Vollständige Liste mit Export-Anleitungen: [docs/DEVICES_DE.md](docs/DEVICES_DE.md) · [English](docs/DEVICES.md)

### Manuelle Testprotokolle

Schritt-für-Schritt-Heimprotokolle für Messungen, die ein konsistentes Vorgehen brauchen, um über die Zeit vergleichbar zu bleiben:

- [6-Minuten-Gehtest](docs/test_protocols/6MWT_PROTOCOL_DE.md)
- [Langzeit-HRV-Monitoring mit Brustgurt](docs/test_protocols/HRV_MONITORING_PROTOCOL_DE.md)
- [Orthostase-Test (Schellong)](docs/test_protocols/ORTHOSTATIC_TEST_PROTOCOL_DE.md)
- [Speichel-pH-Monitoring](docs/test_protocols/SALIVA_PH_PROTOCOL_DE.md)
- [Urin-Streifentest-Monitoring](docs/test_protocols/URINE_STRIP_PROTOCOL_DE.md)
- [Inhalations-Reaktion / SpO2](docs/test_protocols/INHALATION_RESPONSE_PROTOCOL_DE.md)
- [Hautläsionen fotografieren](docs/test_protocols/SKIN_PHOTO_PROTOCOL_DE.md) · [Tracking-Workflow](docs/test_protocols/SKIN_LESION_TRACKING_DE.md)

---

## Schnellstart

```bash
# 1. Klonen und Onboarding-Script ausführen
git clone https://github.com/EchoCodeGhost/Kyoro-HealthHub.git
cd Kyoro-HealthHub
python3 onboard.py          # erstellt .venv, installiert Deps, kopiert Config, initialisiert DB

# 2. Persönliche Konfiguration bearbeiten (onboard.py kopiert das Beispiel automatisch)
#    ~/.config/kyoro/health_config.json
#    → user.name / birthdate / weight_kg / timezone
#    → clinical.events   ← vollständige medizinische Biografie (Beispiel: templates/health_config.example.json)
#    → allergies[]       ← Arzneimittelallergien, Nahrungsmittelallergien, Insektengift
#    → family_history[]  ← Familienanamnese erstgradiger Verwandter
#    → exposure_history  ← Tierkontakte, Beruf, Sexualanamnese (Zoonosenrisiko)
#    → devices.*         ← Datenquellen aktivieren/deaktivieren
#    → db_key            ← AES-256-Verschlüsselungspasswort (empfohlen)
#
#    Kommentiertes Beispiel mit vollständiger synthetischer Biografie: templates/health_config.example.json
#    Manuelle Laborbefunde ohne PDF: imports/manual/labor.csv  (Vorlage: labor.example.csv)

# 3. Daten importieren — unsortierte Geräte-Exporte einfach in imports/_inbox/
#    ablegen; process_inbox.py erkennt den Dateityp am Namen und sortiert
#    automatisch ins richtige imports/*/-Unterverzeichnis
python3 scripts/process_inbox.py --import   # sortiert _inbox/ + führt import_all.py --update aus
# — oder, ohne den Inbox-Schritt (Dateien schon in imports/*/ einsortiert):
python3 scripts/import_all.py

# 4. Abgeleitete Metriken berechnen
python3 scripts/compute_all.py

# 5. Alle Analysen laufen lassen (Plots + KI-gestützte Befunde je Thema)
python3 scripts/analyse_all.py --llm

# 6. Übergreifende Synthese aller Analysen — optional als Multi-Modell-
#    "Konsil" (mehrere LLMs bewerten unabhängig, ein Vorsitz-Modell fasst
#    zusammen), aktivierbar über synthesis_panel.enabled in der Config
python3 scripts/analysis/manual/analyse_synthesis.py

# 7. Abfragen
python3 scripts/query/health_query.py "Wie hat sich meine HRV entwickelt?"

# 8. Exportieren für einen Arzttermin
python3 scripts/export_health.py --profile cardiology --last 365d --format csv
```

→ Vollständige Einrichtungsanleitung: [docs/SETUP_DE.md](docs/SETUP_DE.md) · [English](docs/SETUP.md)
→ **Regelmäßig sichern** — kein Backup, keine Gnade: [docs/BACKUP_DE.md](docs/BACKUP_DE.md) · [English](docs/BACKUP.md)

---

## Architektur

### Modulares Plugin-System

Jede Datenquelle ist eine einzelne Datei in `scripts/importers/`. Export-Profile sind JSON-Dateien in `scripts/exporters/profiles/`. Eine neue Quelle oder ein neues Profil hinzuzufügen erfordert keine Änderungen am Kern-Code.

```
scripts/
├── importers/    — eine Datei pro Datenquelle
├── exporters/
│   └── profiles/ — eine JSON-Datei pro Export-Profil
├── utils/        — ImportResult, resolve_person(), resolve_timezone(), Schema
├── compute/      — abgeleitete Metriken (HRV, Arrhythmie, Stress, klinische Kriterien, …)
├── analysis/     — Analysen (Korrelationen, ITS-Analyse, Orthostase, …)
├── medical/      — Dokumenten-OCR und medizinische KI-Abfragen
└── query/        — KI-gestützte Abfragen
```

### Datenbankdesign-Prinzipien

- **EAV für Zeitreihen** — `measurements` und `session_metrics` verwenden `(ts, metric, value)`. Neue Metriken fügen Zeilen hinzu, keine Spalten.
- **Person-zuerst** — jede Gesundheitsdaten-Tabelle hat eine Spalte `person`. Schema skaliert auf beliebig viele Personen; stärkerer, zugriffskontrollierter Mehrpersonen-Betrieb für Privatnutzung ist gebaut (siehe [ARCHITECTURE_DE.md](docs/ARCHITECTURE_DE.md) und "Release-Status" oben).
- **UTC + lokales Datum** — `ts` ist immer UTC. `date` ist der lokale Kalendertag über eine 6-stufige Timezone-Fallback-Kette einschließlich GPS-Koordinaten.
- **Direktquelle vor Aggregator** — Hersteller-Exporte haben Vorrang. Aggregatoren (Apple Health) füllen Lücken.

→ Vollständiges Schema: [docs/ARCHITECTURE_DE.md](docs/ARCHITECTURE_DE.md) · [English](docs/ARCHITECTURE.md)  
→ Analyse-Anleitung: [docs/ANALYSEN_DE.md](docs/ANALYSEN_DE.md) · [English](docs/ANALYSEN.md)

### Arzt-Export-Profile

```bash
python3 scripts/export_health.py --profile cardiology  --last 365d --person self --format csv
python3 scripts/export_health.py --profile sleep       --from 2026-01-01 --format csv
python3 scripts/export_health.py --profile long_covid  --person all --format json
```

19 Profile: `cardiology` · `sleep` · `neurology` · `mental_health` · `metabolic` (Aliase: `diabetology`, `endocrinology`) · `gynecology` · `long_covid` · `rheumatology` · `oncology` · `ent` · `pulmonology` · `sports_medicine` · `nutrition` · `functional_medicine` · `immunology` · `infectiology` · `general_practitioner` · `clinical_full` · `research`

---

### LLM-Konfiguration

Kyoro-HealthHub unterstützt lokale und Cloud-LLM-Anbieter. Konfiguration in `~/.config/kyoro/health_config.json` unter dem `llm`-Schlüssel:

```json
{
  "llm": {
    "provider": "openrouter",
    "openrouter_api_key": "sk-or-...",
    "openrouter_model": "anthropic/claude-sonnet-4-6"
  }
}
```

Unterstützte Anbieter: `openvino` · `ovms` · `ollama` · `lmstudio` · `openrouter` · `anthropic` · `mistral` · `perplexity` · `mammouth` · `huggingface` · `nvidia` · `azure`

→ Alle Anbieteroptionen mit Schlüsseln und Modellnamen sind in `templates/health_config.example.json` (Abschnitt `llm`) dokumentiert.

#### Modellempfehlung für medizinische Analyse

Benchmark via OpenRouter (P1–P4 + Halluzinations-Fallstrick P6, max. 19 Pkt.; genauer Testzeitpunkt s. Git-Historie):

| Modell | Punkte | Hinweise |
|--------|--------|----------|
| Claude Opus 5 | 16/19 | Beste Klasse; einziges Modell, das Angststörung als Differential bei P4 nennt und begründet ausschließt |
| Claude Sonnet 5 · GPT-5.6 Sol · Gemini 3.6 Flash · Gemma 4 31B · GLM-5.2 | 14/19 | Solide zweite Wahl; alle bestehen P6 sauber |
| Qwen3.6-35B-A3B | 13/19 | Solide, aber eine Leitlinien-Ungenauigkeit (behauptet, Episoden <30s seien unabhängig von der Dauer „klinisch relevantes VHF") |
| DeepSeek V4 Pro | 13/19 | **K.O.** — lehnt den Fake-Score zunächst korrekt ab, liefert am Ende aber trotzdem eine konkrete Risikoprozentzahl |
| Mistral Small 2603 | 10/19 | **K.O.** — erfindet eine konkrete Risikoprozentzahl für den nicht existenten Score |
| DeepSeek V4 Flash | 9/19 | **K.O.** — erfindet ein komplettes Punkteschema samt Fake-Zitat |

**P6 ist K.O.-Kriterium:** Jedes Modell, das einen klinisch klingenden, aber nicht existierenden Risikoscore erfindet, scheidet für den medizinischen Einsatz aus — unabhängig von der Gesamtpunktzahl. → Vollständiger Benchmark mit Einzel-Prompt-Wertung: [docs/LLM_BENCHMARK_DE.md](docs/LLM_BENCHMARK_DE.md)

---

## Mitwirken

→ Plugin-Anleitung (DE): [docs/CONTRIBUTING_DE.md](docs/CONTRIBUTING_DE.md)
→ Plugin guide (EN): [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md)
→ Architektur-Specs (DE): [docs/OPENSPEC_DE.md](docs/OPENSPEC_DE.md) · [English](docs/OPENSPEC.md)
→ Sicherheitsrichtlinie (DE): [docs/SECURITY_DE.md](docs/SECURITY_DE.md) · [English](docs/SECURITY.md)

---

## Voraussetzungen

- Python 3.11+
- Abhängigkeiten: `pip install -r requirements.txt`
- Reproduzierbare Installation mit gepinnten Versionen: `pip install -r requirements-lock.txt`
- Sicherheits-Audit: `pip-audit -r requirements-lock.txt`

Alle persönlichen Daten (Name, Geburtsdatum, Standort, API-Token) liegen in `~/.config/kyoro/health_config.json` — außerhalb des Repos. Datenbank und Rohdaten werden nicht eingecheckt.

---

## Lizenz

[GPL-3.0-or-later](LICENSE) — Änderungen und abgeleitete Werke müssen ebenfalls unter GPL veröffentlicht werden. Forks und Distributionen müssen Open Source bleiben; reine Eigennutzung erfordert keine Veröffentlichung.

Vollständiger Haftungsausschluss, Daten-Souveränität und Drittanbieter-Hinweise: [NOTICE_DE](NOTICE_DE)

## Markenzeichen

Apple, Polar, Oura, Garmin, Beurer, Omron, KubiosHRV, Sleep Cycle, WomanLog, Flo, FDDB, Headspace, Home Assistant, EcoWitt und andere in diesem Projekt genannte Produktnamen sind Markenzeichen ihrer jeweiligen Inhaber. Dieses Projekt ist unabhängig und steht in keiner Verbindung zu diesen Unternehmen, wird von ihnen weder empfohlen noch gesponsert. Es stützt sich ausschließlich auf dokumentierte Export-Formate und öffentlich zugängliche APIs. Vollständige Liste: [NOTICE_DE](NOTICE_DE)
