// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 Kyoro-HealthHub contributors

import Foundation
import SwiftData

/// One symptom observation entered on the phone.
@Model
final class SymptomEntry {
    @Attribute(.unique) var id: UUID
    var timestamp: Date
    /// Key from config/symptom_map.json in the hub.
    var hubKey: String
    var category: String
    /// Severity 0 to 10, as used by the hub's symptoms table.
    var severity: Int
    var note: String?
    /// Set once the entry has been delivered to the hub, so the autopilot never sends it twice.
    var deliveredAt: Date?

    init(hubKey: String, category: String, severity: Int, note: String? = nil, timestamp: Date = .now) {
        self.id = UUID()
        self.timestamp = timestamp
        self.hubKey = hubKey
        self.category = category
        self.severity = min(max(severity, 0), 10)
        self.note = note
    }
}

/// What the user told us during onboarding. Drives suggestions, never diagnoses.
@Model
final class UserSetup {
    var completedOnboardingAt: Date?
    /// Raw values of `Focus`.
    var focusAreas: [String]
    var healthKitRequested: Bool
    var hubPaired: Bool
    var dailyReminderHour: Int?

    init() {
        focusAreas = []
        healthKitRequested = false
        hubPaired = false
    }
}

/// The four phases from the project README, offered as goals in onboarding.
enum Focus: String, CaseIterable, Identifiable, Sendable {
    case understand, treat, optimise, longevity

    var id: String { rawValue }

    var title: String {
        switch self {
        case .understand: "Verstehen, was los ist"
        case .treat: "Behandlung begleiten"
        case .optimise: "Risikofaktoren angehen"
        case .longevity: "Langfristig gesund bleiben"
        }
    }

    var detail: String {
        switch self {
        case .understand: "Beschwerden, Daten und Ereignisse auf einer Zeitachse sehen."
        case .treat: "Wirkung von Therapien und Medikamenten im Verlauf verfolgen."
        case .optimise: "Schlaf, Belastung und Erholung gezielt verbessern."
        case .longevity: "Vorsorge und Trends im Blick behalten."
        }
    }

    var systemImage: String {
        switch self {
        case .understand: "magnifyingglass"
        case .treat: "cross.case"
        case .optimise: "slider.horizontal.3"
        case .longevity: "leaf"
        }
    }
}
