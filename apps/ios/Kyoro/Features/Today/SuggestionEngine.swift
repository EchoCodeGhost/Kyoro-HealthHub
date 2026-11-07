// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 Kyoro-HealthHub contributors
//
// Rule-based "next best action". Deterministic and offline on purpose: every
// suggestion carries the reason it appears, so the user can trust it. The app
// works without a computer; pairing is offered only where it adds something.

import Foundation

struct Suggestion: Identifiable, Equatable, Sendable {
    enum Action: Equatable, Sendable {
        case logSymptom
        case connectHealth
        case runAutopilot
        case startProtocol(TestProtocolID)
    }

    let id: String
    let title: String
    /// Why this card is shown right now. Always present.
    let reason: String
    let actionTitle: String
    let systemImage: String
    let action: Action
    /// Higher comes first.
    let priority: Int
}

struct SuggestionContext: Sendable {
    var now: Date
    var focusAreas: Set<Focus>
    var healthKitRequested: Bool
    var hubPaired: Bool
    var lastSymptomLog: Date?
    var undeliveredEntries: Int
    var calendar: Calendar = .current
}

enum SuggestionEngine {
    static func suggestions(for context: SuggestionContext, limit: Int = KyoroTheme.maxVisibleSuggestions) -> [Suggestion] {
        var result: [Suggestion] = []

        let loggedToday = context.lastSymptomLog.map { context.calendar.isDate($0, inSameDayAs: context.now) } ?? false
        if !loggedToday {
            result.append(Suggestion(
                id: "log-today",
                title: "Wie geht es dir heute?",
                reason: "Für heute gibt es noch keinen Eintrag. Auch „keine Beschwerden“ ist ein wertvoller Datenpunkt.",
                actionTitle: "Symptom erfassen",
                systemImage: "plus.circle",
                action: .logSymptom,
                priority: 90
            ))
        }

        if !context.healthKitRequested {
            result.append(Suggestion(
                id: "connect-health",
                title: "Apple Health freigeben",
                reason: "Dann holt Kyoro Herz-, Schlaf- und Aktivitätsdaten selbst, ohne Export-Datei.",
                actionTitle: "Freigabe einrichten",
                systemImage: "heart.text.square",
                action: .connectHealth,
                priority: 80
            ))
        }

        if context.hubPaired && context.undeliveredEntries > 0 {
            result.append(Suggestion(
                id: "run-autopilot",
                title: "Neue Einträge auswerten",
                reason: context.undeliveredEntries == 1
                    ? "1 Eintrag wartet auf deinen Rechner."
                    : "\(context.undeliveredEntries) Einträge warten auf deinen Rechner.",
                actionTitle: "Jetzt auswerten",
                systemImage: "arrow.triangle.2.circlepath",
                action: .runAutopilot,
                priority: 60
            ))
        }

        if context.focusAreas.contains(.understand) {
            result.append(Suggestion(
                id: "protocol-orthostatic",
                title: "Stehtest machen",
                reason: "Passt zu deinem Ziel „Verstehen“: zeigt, wie Puls und Blutdruck auf Aufstehen reagieren. Der Assistent führt Schritt für Schritt.",
                actionTitle: "Test starten",
                systemImage: "figure.stand",
                action: .startProtocol(.orthostatic),
                priority: 40
            ))
        }

        return Array(result.sorted { $0.priority > $1.priority }.prefix(limit))
    }
}
