// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 Kyoro-HealthHub contributors
//
// Quick-pick symptoms. `hubKey` must be a key of config/symptom_map.json in the
// hub, so imported entries map to the canonical symptom without manual cleanup.
// The full catalogue will be loaded from the hub once paired; this list is the
// offline starting set.

import Foundation

struct SymptomDefinition: Identifiable, Hashable, Sendable {
    let hubKey: String
    let displayName: String
    let category: String
    let systemImage: String

    var id: String { hubKey }
}

enum SymptomCatalog {
    static let quickPick: [SymptomDefinition] = [
        .init(hubKey: "erschöpfung/fatigue", displayName: "Erschöpfung", category: "general", systemImage: "battery.25percent"),
        .init(hubKey: "kopfschmerzen", displayName: "Kopfschmerzen", category: "neurological", systemImage: "brain.head.profile"),
        .init(hubKey: "schwindel", displayName: "Schwindel", category: "neurological", systemImage: "tornado"),
        .init(hubKey: "herzrasen", displayName: "Herzrasen", category: "cardiovascular", systemImage: "heart.text.square"),
        .init(hubKey: "übelkeit", displayName: "Übelkeit", category: "gastrointestinal", systemImage: "stomach"),
        .init(hubKey: "bauchschmerzen", displayName: "Bauchschmerzen", category: "gastrointestinal", systemImage: "bandage"),
        .init(hubKey: "gelenkschmerzen", displayName: "Gelenkschmerzen", category: "musculoskeletal", systemImage: "figure.walk"),
        .init(hubKey: "muskelschmerzen", displayName: "Muskelschmerzen", category: "musculoskeletal", systemImage: "figure.strengthtraining.traditional"),
    ]

    static func definition(for hubKey: String) -> SymptomDefinition? {
        quickPick.first { $0.hubKey == hubKey }
    }
}
