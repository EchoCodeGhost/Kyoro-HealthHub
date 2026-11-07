# Kyoro fürs iPhone (Entwicklungszweig)

> **English version:** [README.md](README.md)

Native iPhone-App, die Kyoro einfach, geführt und eingebunden macht: schnelles
Erfassen, Apple Health, Widgets und Siri, und die Kyoro-Pipeline läuft im
eingebetteten Python direkt auf iPhone oder iPad. Ein Rechner mit dem Hub ist
optional. Plan und Recherche:
`openspec/changes/add-ios-companion-app/`.

> Nicht Teil eines Releases. Wie `mobile/` und `pwa/` braucht die App vor einer
> Veröffentlichung einen vollständigen Privacy-Sweep. Kein Medizinprodukt; siehe
> [NOTICE_DE](../../NOTICE_DE).

## Was im Grundgerüst funktioniert

- Fünf Tabs: Heute, Erfassen, Verlauf, Arzt, Mehr
- Onboarding in vier Schritten (Ziele, Apple-Health-Freigaben mit Begründung, tägliche Erinnerung)
- Regelbasierte Vorschläge auf „Heute“, höchstens drei, jeweils mit Grund
- Symptom erfassen in zwei Tipps; interaktives Widget und Siri-Kurzbefehl „Symptom erfassen“
- Geführter Stehtest (Schellong / NASA Lean Test) mit Checkliste und Timern
- Export der Einträge als `symptomtrack_export_<Datum>.json`, den `scripts/process_inbox.py`
  erkennt und importiert
- Arzt-Tab: Fachrichtung wählen (Export auf dem Gerät folgt mit dem eingebetteten Python)

Noch nicht: Pipeline im eingebetteten Python (Machbarkeitsnachweis in `apps/ios-python-poc`), optionale Hub-Bridge, Autopilot, Lesen von HealthKit-Daten über die
Freigabe hinaus, Speichern von Messwerten aus Protokollen, Fortsetzen pausierter Abläufe.

## Bauen

Benötigt Xcode 26 und [XcodeGen](https://github.com/yonaskolb/XcodeGen).

```bash
cd apps/ios
xcodegen generate
open Kyoro.xcodeproj
```

Eigenes Development-Team in Xcode setzen. HealthKit und App Groups brauchen auf
einem echten Gerät einen bezahlten Entwickleraccount; der Simulator geht ohne.

## Regeln für jede Änderung

- Farben, Abstände und Radien nur aus `Kyoro/DesignSystem/KyoroTheme.swift`
  (Palette aus dem Kyoro-Logo).
- Am Ende jedes Schritts den [No-Slop-Check](NO_SLOP.md) durchgehen.
