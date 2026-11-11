// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 Kyoro-HealthHub contributors

import Foundation
import Testing
@testable import Kyoro

struct SuggestionEngineTests {
    private let now = Date(timeIntervalSince1970: 1_800_000_000)

    private func context(
        focus: Set<Focus> = [],
        health: Bool = true,
        paired: Bool = true,
        lastLog: Date? = nil,
        undelivered: Int = 0
    ) -> SuggestionContext {
        SuggestionContext(
            now: now,
            focusAreas: focus,
            healthKitRequested: health,
            hubPaired: paired,
            lastSymptomLog: lastLog,
            undeliveredEntries: undelivered
        )
    }

    @Test func neverShowsMoreThanTheLimit() {
        let all = context(focus: [.understand], health: false, paired: false)
        #expect(SuggestionEngine.suggestions(for: all).count == KyoroTheme.maxVisibleSuggestions)
    }

    @Test func dailyLogComesFirstWhenNothingLoggedToday() {
        let result = SuggestionEngine.suggestions(for: context(health: false))
        #expect(result.first?.action == .logSymptom)
    }

    @Test func noDailyLogSuggestionAfterLoggingToday() {
        let result = SuggestionEngine.suggestions(for: context(lastLog: now))
        #expect(!result.contains { $0.action == .logSymptom })
    }

    @Test func autopilotOnlyWhenPairedAndSomethingIsWaiting() {
        let waiting = SuggestionEngine.suggestions(for: context(lastLog: now, undelivered: 2))
        #expect(waiting.contains { $0.action == .runAutopilot })

        let unpaired = SuggestionEngine.suggestions(for: context(paired: false, lastLog: now, undelivered: 2))
        #expect(!unpaired.contains { $0.action == .runAutopilot })
        #expect(unpaired.contains { $0.action == .pairHub })
    }

    @Test func everySuggestionExplainsWhy() {
        let all = SuggestionEngine.suggestions(for: context(focus: [.understand], health: false, paired: false), limit: 10)
        #expect(all.allSatisfy { !$0.reason.isEmpty })
    }
}

private let headache = CatalogSymptom(id: "kopfschmerzen", label: "Kopfschmerzen", type: .scale)

struct SymptomExportTests {
    @Test func matchesTheHubImporterFormat() throws {
        let entry = SymptomEntry(symptom: headache, category: "schmerz", value: 6)
        let data = try SymptomExport.encode(SymptomExport.makeFile(from: [entry]))
        let json = try #require(JSONSerialization.jsonObject(with: data) as? [String: Any])
        let entries = try #require(json["symptom_entries"] as? [[String: Any]])

        #expect(entries.count == 1)
        // health.db stores the catalogue label, not the id.
        #expect(entries[0]["symptom"] as? String == "Kopfschmerzen")
        #expect(entries[0]["kategorie"] as? String == "schmerz")
        #expect(entries[0]["wert_num"] as? Int == 6)
        #expect(entries[0]["source"] as? String == "kyoro_ios")
        #expect((entries[0]["timestamp"] as? String)?.count ?? 0 >= 10)
    }

    @Test func textEntriesExportTextOnly() throws {
        let sleep = CatalogSymptom(id: "schlafdauer", label: "Schlafdauer (Stunden)", type: .text)
        let entry = SymptomEntry(symptom: sleep, category: "ressourcen", value: 9, text: "7,5")
        #expect(entry.value == nil)
        #expect(entry.text == "7,5")
    }

    @Test func binaryEntriesStoreOne() {
        let vomit = CatalogSymptom(id: "erbrechen", label: "Erbrechen", type: .binary)
        #expect(SymptomEntry(symptom: vomit, category: "bauchraum").value == 1)
    }

    @Test func fileNameIsRecognisedByTheInbox() {
        #expect(SymptomExport.fileName().hasPrefix("symptomtrack_export_"))
    }

    @Test func valueIsClampedToTheHubScale() {
        #expect(SymptomEntry(symptom: headache, category: "schmerz", value: 14).value == 10)
    }
}

struct SymptomCatalogTests {
    private let json = Data("""
    {"version": 1, "default_modules": ["a"],
     "categories": [{"id": "psyche", "label": "Psyche"}],
     "modules": [
       {"id": "a", "label": "A", "description": "x", "category": "psyche", "default": true,
        "symptoms": [{"id": "s1", "label": "Eins", "type": "scale_inverted"}]},
       {"id": "b", "label": "B", "description": "y", "category": "psyche", "default": false,
        "requires_crisis_notice": true,
        "symptoms": [{"id": "s2", "label": "Zwei", "type": "binary"}]}
     ]}
    """.utf8)

    @Test func decodesTheCatalogueFormat() throws {
        let catalog = try SymptomCatalog.decode(json)
        #expect(catalog.symptom(id: "s1")?.type == .scaleInverted)
        #expect(catalog.modules(active: []).map(\.id) == ["a"])
    }

    @Test func crisisNoticeFollowsTheActiveModules() throws {
        let catalog = try SymptomCatalog.decode(json)
        #expect(!catalog.needsCrisisNotice(active: []))
        #expect(catalog.needsCrisisNotice(active: ["a", "b"]))
    }

    @Test func bundledCatalogueLoads() {
        #expect(!SymptomCatalog.shared.modules.isEmpty)
    }
}
