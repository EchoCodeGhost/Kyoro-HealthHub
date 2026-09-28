# FHIR-Export

## Übersicht

Die FHIR-Export-Funktion ermöglicht das Exportieren von Gesundheitsdaten aus Kyoro HealthHub im FHIR R4-Format. Dies ermöglicht die Interoperabilität mit anderen Gesundheitssystemen, die den FHIR-Standard unterstützen.

## Funktionen

- **FHIR R4-Compliance**: Exportiert Daten im FHIR R4-Format
- **LOINC-Mappings**: Verwendet standardisierte LOINC-Codes für Beobachtungen
- **Ressourcentypen**: Unterstützt Patient, Observation, Condition und MedicationStatement-Ressourcen
- **Verfolgung nicht gemappter Metriken**: Verfolgt und berichtet automatisch über Metriken, die keine LOINC-Mappings haben

## Verwendung

### Grundlegender Export

```bash
python scripts/export_health.py --profile cardiology --format fhir --person self
```

### Export mit Zeitbereich

```bash
python scripts/export_health.py --profile general_practitioner --format fhir \
  --from 2024-01-01 --to 2024-12-31 --person all
```

### Export in bestimmtes Verzeichnis

```bash
python scripts/export_health.py --profile research --format fhir \
  --out /path/to/output/directory
```

## Ausgabedateien

Bei Verwendung von `--format fhir` werden folgende Dateien erstellt:

1. **fhir_bundle.json**: Haupt-FHIR-Bundle mit allen Ressourcen
2. **fhir_export_unmapped_metrics.txt**: Bericht über Metriken, die nicht auf LOINC-Codes gemappt werden konnten (nur erstellt, wenn es nicht gemappte Metriken gibt)
3. **_manifest.json**: Export-Manifest mit Metadaten

## FHIR-Ressourcen

### Patient-Ressource

Minimale Patient-Ressource mit Pseudonym-Identifier:

```json
{
  "resourceType": "Patient",
  "id": "PAT-ABCD",
  "identifier": [{
    "system": "https://kyoro.healthhub/patient",
    "value": "PAT-ABCD"
  }],
  "active": true
}
```

### Observation-Ressource

Observations werden aus Metrikdaten mit LOINC-Codierungen erstellt:

```json
{
  "resourceType": "Observation",
  "id": "obs-123",
  "status": "final",
  "code": {
    "coding": [{
      "system": "http://loinc.org",
      "code": "8867-4",
      "display": "Heart rate"
    }]
  },
  "subject": {
    "reference": "Patient/PAT-ABCD"
  },
  "effectiveDateTime": "2024-01-01T12:00:00Z",
  "valueQuantity": {
    "value": 72,
    "unit": "/min",
    "system": "http://unitsofmeasure.org",
    "code": "/min"
  }
}
```

### Condition-Ressource

Conditions werden aus klinischen Ereignissen mit Diagnose-Typ erstellt:

```json
{
  "resourceType": "Condition",
  "id": "cond-456",
  "clinicalStatus": {
    "coding": [{
      "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
      "code": "active",
      "display": "Active"
    }]
  },
  "verificationStatus": {
    "coding": [{
      "system": "http://terminology.hl7.org/CodeSystem/condition-ver-status",
      "code": "confirmed",
      "display": "Confirmed"
    }]
  },
  "code": {
    "text": "Hypertension"
  },
  "subject": {
    "reference": "Patient/PAT-ABCD"
  },
  "onsetDateTime": "2024-01-01"
}
```

### MedicationStatement-Ressource

MedicationStatements werden aus Medikamentendaten erstellt:

```json
{
  "resourceType": "MedicationStatement",
  "id": "med-001",
  "status": "completed",
  "medicationCodeableConcept": {
    "text": "Ibuprofen"
  },
  "subject": {
    "reference": "Patient/PAT-ABCD"
  },
  "effectiveDateTime": "2024-01-01",
  "dosage": [{
    "text": "200 mg oral",
    "timing": {
      "repeat": {
        "frequency": 1,
        "period": 1,
        "periodUnit": "d"
      }
    },
    "route": {
      "text": "oral"
    },
    "doseAndRate": [{
      "doseQuantity": {
        "value": 200,
        "unit": "mg",
        "system": "http://unitsofmeasure.org",
        "code": "mg"
      }
    }]
  }]
}
```

## FHIR-Bundle-Struktur

Die Hauptausgabe ist ein FHIR-Bundle vom Typ "collection", das alle Ressourcen enthält:

```json
{
  "resourceType": "Bundle",
  "id": "kyoro-export-2024-07-15T12:00:00",
  "type": "collection",
  "timestamp": "2024-07-15T12:00:00Z",
  "entry": [
    {
      "fullUrl": "urn:uuid:PAT-ABCD",
      "resource": { ... }
    },
    {
      "fullUrl": "urn:uuid:obs-123",
      "resource": { ... }
    },
    {
      "fullUrl": "urn:uuid:cond-456",
      "resource": { ... }
    }
  ]
}
```

## LOINC-Mappings

### Aktuelle Mappings

Die folgenden Metriken sind derzeit auf LOINC-Codes gemappt:

| Kyoro-Metrik | LOINC-Code | LOINC-Anzeige |
|--------------|------------|---------------|
| `heart_rate` | 8867-4 | Heart rate |
| `hrv_rmssd` | — | kein bestätigter LOINC-Code gefunden, bewusst unmapped gelassen (s. `fhir_metric_codes.json`, `_pending_verification`) statt geraten |
| `hrv_sdnn` | 80404-7 | R-R interval.standard deviation (Heart rate variability) |
| `oxygen_saturation` | 59408-5 | Oxygen saturation in Arterial blood by Pulse oximetry |
| `total_sleep_min` | 93832-4 | Sleep duration |

### Neue Mappings hinzufügen

Um ein neues Metrik-Mapping hinzuzufügen:

1. **LOINC-Code verifizieren**: Besuchen Sie [loinc.org](https://loinc.org) und suchen Sie nach dem appropriate Code
2. **Mapping-Datei bearbeiten**: Fügen Sie das Mapping zu `scripts/exporters/fhir_metric_codes.json` hinzu
3. **Verifizierungsinformationen hinzufügen**: Fügen Sie `verified_by` und `source_url_or_reference` hinzu

Beispiel:
```json
{
  "mappings": {
    "new_metric": {
      "system": "http://loinc.org",
      "code": "12345-6",
      "display": "New Metric Display Name",
      "verified_by": "Ihr Name",
      "source_url_or_reference": "https://loinc.org/12345-6/"
    }
  }
}
```

### Nicht gemappte Metriken

Metriken, die keine LOINC-Mappings haben, werden im `_unmapped_for_now`-Array aufgelistet und im `fhir_export_unmapped_metrics.txt` berichtet.

Aktuell nicht gemappte Metriken:
- `blood_pressure_systolic`
- `blood_pressure_diastolic`
- `body_weight`
- `body_temperature`
- `respiratory_rate`

## Validierung

Der FHIR-Export enthält grundlegende Validierung:
- Alle erforderlichen Felder sind vorhanden
- Ressourcentypen sind korrekt
- Referenzen zwischen Ressourcen sind gültig

Für vollständige FHIR R4-Validierung verwenden Sie externe Tools wie:
- [HL7 FHIR Validator](https://confluence.hl7.org/display/FHIR/Using+the+FHIR+Validator)
- [HAPI FHIR Validator](https://hapifhir.io/hapi-fhir/docs/validation/)

## Einschränkungen

1. **Nur Export**: Dies ist eine reine Export-Funktion. Kyoro HealthHub unterstützt derzeit keinen FHIR-Import und fungiert nicht als FHIR-Server.
2. **Keine HL7 v2-Unterstützung**: Nur FHIR R4-Format wird unterstützt.
3. **Begrenzte Ressourcentypen**: Unterstützt derzeit Patient, Observation, Condition und MedicationStatement.
4. **Manuelle Code-Verifizierung**: LOINC/SNOMED-Codes müssen manuell verifiziert werden, bevor sie zur Mapping-Datei hinzugefügt werden.

## Compliance

- **Datenschutz**: Alle Exporte verwenden Pseudonyme, keine echten Namen oder identifizierbaren Informationen
- **Datenminimierung**: Nur die im Export-Profil spezifizierten Daten sind enthalten
- **Audit-Trail**: Exporte werden in den System-Access-Logs protokolliert

## Fehlerbehebung

### Kein FHIR-Bundle erstellt

- Überprüfen Sie, ob das Export-Profil Abfragen mit Metrikdaten enthält
- Verifizieren Sie, dass die Metriken LOINC-Mappings in `fhir_metric_codes.json` haben
- Überprüfen Sie die Konsolenausgabe auf Fehlermeldungen

### Bericht über nicht gemappte Metriken

Wenn Sie viele nicht gemappte Metriken sehen:
- Überprüfen Sie `fhir_export_unmapped_metrics.txt` für die Liste
- Erwägen Sie, LOINC-Mappings für häufig verwendete Metriken hinzuzufügen
- Verifizieren Sie, dass Ihre Daten die erwarteten Metrik-Namen verwenden

### Validierungsfehler

Verwenden Sie externe FHIR-Validatoren, um das Bundle zu überprüfen:
```bash
# Beispiel mit HAPI-Validator
java -jar fhir-validator-cli.jar fhir_bundle.json
```

## Wohin ein Export gehen könnte (manuell, nicht automatisiert)

Kyoro lädt nichts selbstständig hoch und überträgt nichts — jeder Export
(`export_research_cohort.py`, dieser FHIR-Export) schreibt ausschließlich
eine lokale Datei. Wer einen anonymisierten Export der Forschung spenden
möchte, muss ihn selbst einreichen. Dieser Abschnitt dokumentiert nur
realistisch existierende Ziele — keine Empfehlung für das eine gegenüber
dem anderen, und keine rechtliche oder ethische Beratung dazu, ob die
Spende der eigenen Daten für einen selbst richtig ist.

**[Zenodo](https://zenodo.org/)** (von CERN betrieben) — allgemeines
Forschungsdatenrepositorium. Keine institutionelle Zugehörigkeit nötig,
kostenloser Account, bis 50GB pro Upload, jeder Dateityp, sofortige
DOI-Vergabe bei Veröffentlichung. Unterstützt **restricted access** (nicht
nur voll öffentlich) — relevant, wenn der Export auffindbar/zitierbar,
aber nicht für jeden frei herunterladbar sein soll. Passt direkt für ein
FHIR-Bundle oder einen Forschungs-Kohorten-CSV-Export so, wie er ist.

**[PhysioNet](https://physionet.org/)** — Repositorium speziell für
physiologische/Wearable-Signaldaten (EKG, HRV u.ä.), erreicht die
Forschungscommunity, die tatsächlich mit solchen Daten arbeitet, direkter
als ein allgemeines Repositorium. Kostenloser PhysioNetWorks-Account,
dann ein Projekt mit den eigenen Dateien plus einem kurzen README zur
Beschreibung des Datensatzes. Formeller als Zenodo (vergleichbar mit
einer Zeitschrifteneinreichung) und verlangt rechtlich vorherige
Anonymisierung — genau wofür der k-Anonymität-/Datumsverschiebungs-Schritt
in `export_research_cohort.py` da ist.

**DeSci ("Decentralized Science")** — selbst kein Einreichungsziel,
sondern Hintergrundwissen, das bei der Abwägung hilft, wohin eine Spende
gehen könnte. DeSci ist ein Bündel von Finanzierungs-/Publikations-
Mechanismen (IP-NFTs, themenspezifische DAOs, Quadratic Funding), das
genau den Engpass umgehen soll, der Nischen- oder unkonventionelle
Forschung am härtesten trifft: klassische Förderinstitutionen sind
langsam, risikoscheu und auf wenige Stellen konzentriert, weshalb
unterfinanzierte Forschungsfelder (z.B. Longevity-/Alternsforschung,
ME/CFS, Long-COVID, andere postinfektiöse oder seltene Erkrankungen)
selbst bei solider Wissenschaft oft keine Förderung dort bekommen.
DeSci-Mechanismen lassen viele kleine Geldgeber ein Projekt direkt
unterstützen, statt auf einen einzelnen großen Gatekeeper zu warten, und
manche DeSci-geförderten Gruppen suchen aktiv genau die Art
longitudinaler, patientengeführter Daten, die ein solcher Export enthält.
Konkreter Einstiegspunkt: **[VitaDAO](https://www.vitadao.com/)**
finanziert Longevity-/Alternsforschung über eine community-gesteuerte
Kasse und ist das etablierteste Beispiel für dieses Modell. Der Großteil
der DeSci-Finanzierungsaktivität läuft aktuell auf **Ethereum** — VitaDAO
und die meisten vergleichbaren Projekte bauen auf Ethereum-Infrastruktur
auf, und Ethereum-Mitgründer Vitalik Buterin ist ein öffentlich bekannter
Unterstützer/Geldgeber speziell von VitaDAO sowie von DeSci und
Longevity-Forschung allgemeiner. Kyoro selbst hat keine
Blockchain-Komponente und ist kein DeSci-Projekt — hier geht es rein um
einen Finanzierungs-/Community-Aspekt, der bei der Entscheidung, wohin
ein gespendeter Export den größten Nutzen bringen könnte, relevant sein
kann.

**Konkrete Institutionen/Forschungsgruppen** (z.B. die Long-COVID-/
ME-CFS- oder Kardiologie-Forschungsgruppe einer Universitätsklinik) — ein
anderer Weg als die beiden Selbstbedienungs-Repositorien oben: es gibt
kein generisches Upload-Portal, man kontaktiert eine konkrete
Forschungsgruppe direkt und fragt, ob sie die Daten haben möchte — meist
über deren eigenes Einwilligungs-/Ethikverfahren, nicht nur über Kyoros
Export allein. Am besten geeignet, wenn schon ein echter Bezug besteht
(eine bestehende klinische Beziehung, eine Gruppe, deren veröffentlichtes
Forschungsthema genau zu den Daten passt) statt einer Kalteinreichung.

Vor jeder Einreichung: die Manifest-/Einwilligungsaufzeichnungen des
Exports nochmal durchlesen, und die Datenteilungsrichtlinie des jeweiligen
Ziels für gesundheitsnahe Daten prüfen — die Anforderungen unterscheiden
sich je Plattform und können sich ändern.

## Zukünftige Erweiterungen

- Unterstützung für weitere FHIR-Ressourcentypen
- Implementierung der automatischen LOINC-Code-Suche (mit menschlicher Verifizierung)
- Hinzufügen von FHIR-Schema-Validierung
- Unterstützung für SNOMED-CT-Codes zusätzlich zu LOINC
- Implementierung von FHIR-Suchparametern im Export

## Referenzen

- [HL7 FHIR R4-Spezifikation](http://hl7.org/fhir/R4/)
- [LOINC-Benutzerhandbuch](https://loinc.org/usage/guide/)
- [UCUM-Einheiten-Spezifikation](https://ucum.org/ucum.html)
- [FHIR-Bundle-Ressource](http://hl7.org/fhir/R4/bundle.html)

## Siehe auch

- [Export-Profile](../README.md#doctor-export-profiles) — Profilliste und Nutzung im README
- [Privacy-Architektur](PRIVACY_ARCHITECTURE.md)
- [Contributing-Guide](CONTRIBUTING_DE.md)