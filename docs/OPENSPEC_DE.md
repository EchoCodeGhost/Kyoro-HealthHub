# OpenSpec

> **English version:** [OPENSPEC.md](OPENSPEC.md)

Kyoro-HealthHub nutzt [OpenSpec](https://openspec.dev/), um architektonische
Anforderungen als lebendige, versionierte Specs neben dem Code zu pflegen —
getrennt von der pro-Skript-Dokumentation, die aus Docstrings generiert wird
(siehe [docstring_onboarding_guide_DE.md](docstring_onboarding_guide_DE.md)).

---

## Warum

CLAUDE.md und die generierten Skript-Docs beschreiben, *wie* der Code
funktioniert. OpenSpec-Specs beschreiben, *was das System leisten muss* — in
einer Form, die eine einzelne Chat-Session überlebt und bei Änderungen
diffbar ist. Das ist besonders für Contributor:innen relevant, die nach dem
Release dazustoßen und einen strukturierten Einstiegspunkt jenseits der
kompletten Codebase brauchen.

## Wo die Specs liegen

```
openspec/
├── config.yaml        — Projektkontext, der KI-Tools beim Erstellen von Specs angezeigt wird
├── specs/              — aktuelle Baseline: ein spec.md pro Capability
│   ├── pipeline-architecture/
│   ├── db-schema-conventions/
│   ├── privacy-rules/
│   ├── importer-pattern/
│   └── … (14 Capabilities insgesamt, s. Tabelle unten)
└── changes/
    ├── <proposal-name>/  — aktive Change-Proposals in Arbeit (proposal.md, design.md, tasks.md)
    ├── …
    └── archive/           — abgeschlossene Change-Proposals, in specs/ übernommen
```

Jede `spec.md` enthält `### Requirement:`-Blöcke mit
`#### Scenario:`-Abschnitten im WHEN/THEN-Format — testbare Aussagen, kein
Fließtext.

## Aktuelle Baseline-Specs

| Capability | Deckt ab |
|---|---|
| `pipeline-architecture` | Import→Compute→Analyse-Reihenfolge, feste Compute-Abhängigkeitskette, stilles Leerergebnis bei übersprungener Stufe |
| `db-schema-conventions` | EAV-Pattern für Zeitreihen, `person`/`OWN_PERSON_ID`-Konvention, Kompatibilitäts-Views, `INSERT OR IGNORE`, `ts`/`date`-Semantik |
| `privacy-rules` | Kein Diagnose-/Entity-Identifier im Code, keine hartkodierten Zeitzonen, keine Fallback-Dicts mit echten Entity-IDs, Pflicht-Durchlauf von `check_source_privacy.py` |
| `importer-pattern` | Pflicht-`run()`-Signatur, `resolve_person()`/`resolve_timezone()`-Nutzung, atomares `log_import()`, Registrierung in `import_all.py` |
| `cross-cutting-conventions` | Keine hartkodierten Zeitzonen/Geräte/Sprachen in jedem neuen Skript, Umgang mit strukturellen Änderungen und unmöglichen Werten |
| `data-provenance` | Attribution + Code-Versions-Logging bei Import/Migration, Logging von Analyse-Läufen, keine falschen Pro-Person-Zuordnungsansprüche |
| `documentation-conventions` | Konfidenz-Kennzeichnung via `label_finding()`, Pflichtfeld `@relevance.de`/`@relevance.en` im Docstring, bilingualer (DE-zuerst) Inhalt, Docstring-Schema als Single Source of Truth |
| `ethics-enforcement` | Liste verbotener Nutzungen, lokale Speicherung standardmäßig, authentifizierter API-Zugriff, keine Credentials im Code/Log, Datenminimierung beim Import |
| `fhir-export` | FHIR als zusätzliches Export-Format, keine erfundenen Terminologie-Codes, nur pseudonyme Patientenreferenz, Offline-Schema-Validierung, reiner Export ohne Netzwerkübertragung |
| `identifier-pseudonymization` | Zentrales `identity_resolver`-Modul, deterministische, lokal gespeicherte gesalzene Pseudonyme, `sensor_type`-basiertes Geräte-Routing statt rohem Geräte-Pseudonym |
| `image-importer-pattern` | Pflicht-PII-Entfernung bei Foto-/Bildimporten, GPS-Erfassung vor Verwerfen, RAW+Vorschau-Aufbewahrung, Seriennummern-Pseudonymisierung auch für RAW, Standortdaten nur in medizinisch relevanten Analysen |
| `privacy-by-design-access-control` | Gleichrangige private Nutzungskontexte, Security/Privacy by Design und by Default, Anonymisierung zuerst mit Pseudonymisierung als Mindeststandard, getestete Mehrbenutzer-Autorisierung |
| `reference-device-configuration` | Pro-Metrik konfigurierbares Referenzgerät mit hartkodiertem Fallback, konfigurationsgesteuerte Anker in `compute_calibrate_sources.py`/`compute_pem.py`, Auflösung über `device_registry.source_apps` |
| `research-cohort-export` | Freigabe-gebundene Instanz-Einbindung, deterministische Pro-Patient-Datumsverschiebung, Altersbänderung, k-Anonymität-Durchsetzung, ausschließlich lokale Ausgabe |

Die ersten vier wurden als **Brownfield-Baseline** verfasst: Sie dokumentieren
Verhalten, das zum Zeitpunkt der Erstellung bereits im Code und in
CLAUDE.md existierte — es wurde keine Funktionalität geändert. Die übrigen
kamen schrittweise hinzu, sobald Change-Proposals archiviert wurden (s.
„Wo die Specs liegen" oben).

## OpenSpec für einen neuen Beitrag nutzen

Ist Claude Code mit der OpenSpec-Integration eingerichtet (`openspec init
--tools claude`), stehen folgende Slash-Commands zur Verfügung:

| Command | Zweck |
|---|---|
| `/opsx:propose` | Beschreibe, was du bauen willst; erzeugt Proposal, Design, Spec-Deltas und Tasks in einem Schritt |
| `/opsx:explore` | Eine Idee oder Anforderung durchdenken, bevor ein Proposal entsteht |
| `/opsx:apply` | Die Tasks einer bestehenden Change umsetzen |
| `/opsx:update` | Artefakte einer bestehenden Change überarbeiten |
| `/opsx:sync` | Spec-Deltas einer Change in die Haupt-Specs übernehmen, ohne zu archivieren |
| `/opsx:archive` | Eine abgeschlossene Change finalisieren und ihre Spec-Deltas in `openspec/specs/` übernehmen |

Typischer Ablauf für einen neuen Importer: `/opsx:propose "Importer für
<Gerät>"` → generiertes Proposal/Spec-Delta gegen
[importer-pattern](../openspec/specs/importer-pattern/spec.md) und
CONTRIBUTING_DE.md prüfen → `/opsx:apply` zur Umsetzung →
`review-importer`-Skill das Ergebnis prüfen lassen → `/opsx:archive` nach
dem Merge.

## Was das nicht ist

- Kein Ersatz für CLAUDE.md (Alltags-Workflow, Befehle, Konventionen) oder
  die Skript-Docs unter `docs/de/`/`docs/en/` (Implementierungsdetails).
- Nicht CI-erzwungen — Specs sind eine Review-Hilfe, kein Laufzeit-Gate.
- Nicht als vollständige Abdeckung der gesamten Codebase gedacht. Neue
  Specs sollten entstehen, wenn sie Contributor:innen bei einem konkreten
  Bereich helfen, nicht als pauschale Dokumentationsübung.
