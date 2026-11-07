// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 Kyoro-HealthHub contributors
//
// Read access only for this step. Each type maps to a hub analysis that uses it,
// so the onboarding can say why it asks (permission priming).

import HealthKit

struct HealthDataGroup: Identifiable, Sendable {
    let id: String
    let title: String
    let reason: String
    let systemImage: String
    let types: [HKObjectType]
}

@MainActor
final class HealthKitService {
    private let store = HKHealthStore()

    static var isAvailable: Bool { HKHealthStore.isHealthDataAvailable() }

    static let groups: [HealthDataGroup] = [
        HealthDataGroup(
            id: "heart",
            title: "Herz und HRV",
            reason: "Für HRV-Trends, Ruhepuls und Hinweise auf Rhythmusauffälligkeiten.",
            systemImage: "heart",
            types: [
                HKQuantityType(.heartRate),
                HKQuantityType(.restingHeartRate),
                HKQuantityType(.heartRateVariabilitySDNN),
                HKObjectType.electrocardiogramType(),
            ]
        ),
        HealthDataGroup(
            id: "sleep",
            title: "Schlaf und Atmung",
            reason: "Für Schlafqualität, nächtliche Sauerstoffsättigung und Erholung.",
            systemImage: "bed.double",
            types: [
                HKCategoryType(.sleepAnalysis),
                HKQuantityType(.oxygenSaturation),
                HKQuantityType(.respiratoryRate),
            ]
        ),
        HealthDataGroup(
            id: "activity",
            title: "Aktivität",
            reason: "Um Belastung und Beschwerden am Folgetag gegenüberzustellen (PEM).",
            systemImage: "figure.walk",
            types: [
                HKQuantityType(.stepCount),
                HKQuantityType(.activeEnergyBurned),
                HKObjectType.workoutType(),
            ]
        ),
        HealthDataGroup(
            id: "body",
            title: "Körper und Blutdruck",
            reason: "Für Gewicht, Körperzusammensetzung und Blutdruckverlauf.",
            systemImage: "scalemass",
            types: [
                HKQuantityType(.bodyMass),
                HKQuantityType(.bloodPressureSystolic),
                HKQuantityType(.bloodPressureDiastolic),
            ]
        ),
    ]

    func requestReadAccess(for groups: [HealthDataGroup]) async throws {
        let types = Set(groups.flatMap(\.types))
        guard Self.isAvailable, !types.isEmpty else { return }
        try await store.requestAuthorization(toShare: [], read: types)
    }
}
