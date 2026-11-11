// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 Kyoro-HealthHub contributors
//
// One intent serves Siri, Shortcuts, Spotlight and the interactive widget, so
// "Symptom erfassen" behaves the same everywhere. It offers the 0-10 symptoms
// of the catalogue; yes/no and text entries need the app.

import AppIntents

struct SymptomAppEntity: AppEntity {
    static let typeDisplayRepresentation: TypeDisplayRepresentation = "Symptom"
    static let defaultQuery = SymptomQuery()

    let id: String
    let name: String

    var displayRepresentation: DisplayRepresentation { DisplayRepresentation(title: "\(name)") }

    init(_ symptom: CatalogSymptom) {
        id = symptom.id
        name = symptom.label
    }
}

struct SymptomQuery: EntityStringQuery {
    private var catalog: SymptomCatalog { .shared }

    private var scaleSymptoms: [CatalogSymptom] {
        var seen = Set<String>()
        return catalog.modules.flatMap(\.symptoms).filter {
            ($0.type == .scale || $0.type == .scaleInverted) && seen.insert($0.id).inserted
        }
    }

    func entities(for identifiers: [String]) async throws -> [SymptomAppEntity] {
        identifiers.compactMap(catalog.symptom(id:)).map(SymptomAppEntity.init)
    }

    func entities(matching string: String) async throws -> [SymptomAppEntity] {
        scaleSymptoms
            .filter { $0.label.localizedStandardContains(string) }
            .map(SymptomAppEntity.init)
    }

    func suggestedEntities() async throws -> [SymptomAppEntity] {
        SharedStore.pinnedSymptomIDs.compactMap(catalog.symptom(id:)).map(SymptomAppEntity.init)
    }
}

struct LogSymptomIntent: AppIntent {
    static let title: LocalizedStringResource = "Symptom erfassen"
    static let description = IntentDescription("Erfasst ein Symptom mit einem Wert von 0 bis 10, ohne die App zu öffnen.")

    @Parameter(title: "Symptom")
    var symptom: SymptomAppEntity

    @Parameter(title: "Wert", description: "0 bis 10", default: 5, inclusiveRange: (0, 10))
    var value: Int

    init() {}

    init(symptom: SymptomAppEntity, value: Int) {
        self.symptom = symptom
        self.value = value
    }

    static var parameterSummary: some ParameterSummary {
        Summary("\(\.$symptom) mit \(\.$value) von 10 erfassen")
    }

    func perform() async throws -> some IntentResult & ProvidesDialog {
        SharedStore.enqueue(QuickLog(symptomID: symptom.id, value: value, timestamp: .now))
        return .result(dialog: "\(symptom.name): \(value) von 10 gespeichert.")
    }
}
