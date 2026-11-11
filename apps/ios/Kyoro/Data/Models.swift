// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 Kyoro-HealthHub contributors

import Foundation
import SwiftData

/// One symptom observation entered on the phone.
///
/// The app is not released yet, so the schema changes without a migration plan.
/// Add a `VersionedSchema` before the first TestFlight build.
@Model
final class SymptomEntry {
    @Attribute(.unique) var id: UUID
    var timestamp: Date
    /// Catalogue id (config/symptom_catalog.json), stable across label edits.
    var symptomID: String
    /// Catalogue label at the time of entry. This is what health.db stores.
    var label: String
    /// Catalogue category id, exported as `kategorie`.
    var category: String
    /// Raw value of `SymptomEntryType`.
    var typeRaw: String
    /// 1 for binary entries, 0 to 10 for scales, nil for text entries.
    var value: Int?
    /// The answer of a text entry, for example "7,5" hours of sleep.
    var text: String?
    var note: String?
    /// Set once the entry has been delivered to the hub, so the autopilot never sends it twice.
    var deliveredAt: Date?

    init(symptom: CatalogSymptom, category: String, value: Int? = nil, text: String? = nil, note: String? = nil, timestamp: Date = .now) {
        self.id = UUID()
        self.timestamp = timestamp
        self.symptomID = symptom.id
        self.label = symptom.label
        self.category = category
        self.typeRaw = symptom.type.rawValue
        switch symptom.type {
        case .binary: self.value = 1
        case .scale, .scaleInverted: self.value = min(max(value ?? 0, 0), 10)
        case .text: self.value = nil
        }
        self.text = symptom.type == .text ? text : nil
        self.note = note
    }

    var type: SymptomEntryType { SymptomEntryType(rawValue: typeRaw) ?? .scale }

    /// Short German value for lists: "eingetragen", "6 von 10" or the text.
    var valueDescription: String {
        switch type {
        case .binary: "eingetragen"
        case .scale, .scaleInverted: "\(value ?? 0) von 10"
        case .text: text ?? ""
        }
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
    /// Catalogue module ids the user tracks. Empty means the catalogue defaults.
    var activeModules: [String] = []

    init() {
        focusAreas = []
        activeModules = []
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
