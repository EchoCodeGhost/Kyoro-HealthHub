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
    }

    @Test func everySuggestionExplainsWhy() {
        let all = SuggestionEngine.suggestions(for: context(focus: [.understand], health: false, paired: false), limit: 10)
        #expect(all.allSatisfy { !$0.reason.isEmpty })
    }
}

struct SymptomExportTests {
    @Test func matchesTheHubImporterFormat() throws {
        let entry = SymptomEntry(hubKey: "kopfschmerzen", category: "neurological", severity: 6)
        let data = try SymptomExport.encode(SymptomExport.makeFile(from: [entry]))
        let json = try #require(JSONSerialization.jsonObject(with: data) as? [String: Any])
        let entries = try #require(json["symptom_entries"] as? [[String: Any]])

        #expect(entries.count == 1)
        #expect(entries[0]["symptom"] as? String == "kopfschmerzen")
        #expect(entries[0]["kategorie"] as? String == "neurological")
        #expect(entries[0]["wert_num"] as? Int == 6)
        #expect((entries[0]["timestamp"] as? String)?.count ?? 0 >= 10)
    }

    @Test func fileNameIsRecognisedByTheInbox() {
        #expect(SymptomExport.fileName().hasPrefix("symptomtrack_export_"))
    }

    @Test func severityIsClampedToTheHubScale() {
        #expect(SymptomEntry(hubKey: "schwindel", category: "neurological", severity: 14).severity == 10)
    }
}
