// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 Kyoro-HealthHub contributors
//
// One intent serves Siri, Shortcuts, Spotlight and the interactive widget, so
// "Symptom erfassen" behaves the same everywhere.

import AppIntents

struct SymptomAppEntity: AppEntity {
    static let typeDisplayRepresentation: TypeDisplayRepresentation = "Symptom"
    static let defaultQuery = SymptomQuery()

    let id: String
    let name: String

    var displayRepresentation: DisplayRepresentation { DisplayRepresentation(title: "\(name)") }

    init(_ definition: SymptomDefinition) {
        id = definition.hubKey
        name = definition.displayName
    }
}

struct SymptomQuery: EntityQuery {
    func entities(for identifiers: [String]) async throws -> [SymptomAppEntity] {
        identifiers.compactMap(SymptomCatalog.definition(for:)).map(SymptomAppEntity.init)
    }

    func suggestedEntities() async throws -> [SymptomAppEntity] {
        SymptomCatalog.quickPick.map(SymptomAppEntity.init)
    }
}

struct LogSymptomIntent: AppIntent {
    static let title: LocalizedStringResource = "Symptom erfassen"
    static let description = IntentDescription("Erfasst ein Symptom mit Stärke, ohne die App zu öffnen.")

    @Parameter(title: "Symptom")
    var symptom: SymptomAppEntity

    @Parameter(title: "Stärke", description: "0 = keine, 10 = stärkste vorstellbare", default: 5, inclusiveRange: (0, 10))
    var severity: Int

    init() {}

    init(symptom: SymptomAppEntity, severity: Int) {
        self.symptom = symptom
        self.severity = severity
    }

    static var parameterSummary: some ParameterSummary {
        Summary("\(\.$symptom) mit Stärke \(\.$severity) erfassen")
    }

    func perform() async throws -> some IntentResult & ProvidesDialog {
        SharedStore.enqueue(QuickLog(hubKey: symptom.id, severity: severity, timestamp: .now))
        return .result(dialog: "\(symptom.name) mit Stärke \(severity) gespeichert.")
    }
}
