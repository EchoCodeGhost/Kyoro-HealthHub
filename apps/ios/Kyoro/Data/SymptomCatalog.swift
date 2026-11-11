// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 Kyoro-HealthHub contributors
//
// The shared symptom catalogue (config/symptom_catalog.json in the repository,
// bundled into the app and the widget). The same file drives Kyoro SymptomTrack
// and the hub, so a symptom's `label` is exactly the value stored in
// health.db's symptoms.symptom column. Never rename a label in the app.

import Foundation

enum SymptomEntryType: String, Codable, Sendable {
    /// Present or not (stored as 1).
    case binary
    /// 0 to 10, high means worse.
    case scale
    /// 0 to 10, high means better (energy, mood, sleep quality).
    case scaleInverted = "scale_inverted"
    /// Free text, for example sleep duration.
    case text
}

struct CatalogSymptom: Codable, Identifiable, Hashable, Sendable {
    let id: String
    let label: String
    let type: SymptomEntryType
}

struct CatalogCategory: Codable, Identifiable, Hashable, Sendable {
    let id: String
    let label: String
}

struct CatalogModule: Decodable, Identifiable, Hashable, Sendable {
    let id: String
    let label: String
    let description: String
    let category: String
    /// Episode form the module belongs to ("migraine"); used once episodes land (task 4d.6).
    let episode: String?
    let requiresCrisisNotice: Bool
    let symptoms: [CatalogSymptom]

    enum CodingKeys: String, CodingKey {
        case id, label, description, category, episode, symptoms
        case requiresCrisisNotice = "requires_crisis_notice"
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = try c.decode(String.self, forKey: .id)
        label = try c.decode(String.self, forKey: .label)
        description = try c.decode(String.self, forKey: .description)
        category = try c.decode(String.self, forKey: .category)
        episode = try c.decodeIfPresent(String.self, forKey: .episode)
        requiresCrisisNotice = try c.decodeIfPresent(Bool.self, forKey: .requiresCrisisNotice) ?? false
        symptoms = try c.decode([CatalogSymptom].self, forKey: .symptoms)
    }
}

struct SymptomCatalog: Decodable, Sendable {
    let version: Int
    let defaultModules: [String]
    let categories: [CatalogCategory]
    let modules: [CatalogModule]

    enum CodingKeys: String, CodingKey {
        case version, categories, modules
        case defaultModules = "default_modules"
    }

    /// The bundled catalogue. A missing or broken file is a build error, not a runtime state.
    static let shared: SymptomCatalog = {
        guard let url = Bundle.main.url(forResource: "symptom_catalog", withExtension: "json"),
              let data = try? Data(contentsOf: url),
              let catalog = try? decode(data)
        else {
            fatalError("symptom_catalog.json fehlt im App-Bundle oder ist ungültig.")
        }
        return catalog
    }()

    static func decode(_ data: Data) throws -> SymptomCatalog {
        try JSONDecoder().decode(SymptomCatalog.self, from: data)
    }

    func symptom(id: String) -> CatalogSymptom? {
        for module in modules {
            if let match = module.symptoms.first(where: { $0.id == id }) { return match }
        }
        return nil
    }

    func module(containing symptomID: String) -> CatalogModule? {
        modules.first { $0.symptoms.contains { $0.id == symptomID } }
    }

    func category(id: String) -> CatalogCategory? {
        categories.first { $0.id == id }
    }

    /// Active modules in catalogue order. An empty selection means the defaults.
    func modules(active ids: [String]) -> [CatalogModule] {
        let wanted = Set(ids.isEmpty ? defaultModules : ids)
        return modules.filter { wanted.contains($0.id) }
    }

    /// Symptoms of the active modules grouped by category, each symptom once.
    func sections(active ids: [String]) -> [(category: CatalogCategory, symptoms: [CatalogSymptom])] {
        var order: [String] = []
        var grouped: [String: [CatalogSymptom]] = [:]
        var seen = Set<String>()
        for module in modules(active: ids) {
            if grouped[module.category] == nil {
                order.append(module.category)
                grouped[module.category] = []
            }
            for symptom in module.symptoms where seen.insert(symptom.id).inserted {
                grouped[module.category, default: []].append(symptom)
            }
        }
        return order.compactMap { id in
            category(id: id).map { ($0, grouped[id] ?? []) }
        }
    }

    /// True while any active module obliges the crisis notice.
    func needsCrisisNotice(active ids: [String]) -> Bool {
        modules(active: ids).contains { $0.requiresCrisisNotice }
    }

    /// Fallback widget symptoms before the user has logged anything.
    static let defaultPinnedIDs = ["erschoepfung_fatigue", "kopfschmerzen", "uebelkeit", "muskelschmerzen"]
}

extension SymptomEntryType {
    /// Words at the ends of the scale, so a 6 means the same thing to everyone.
    var anchors: (low: String, high: String)? {
        switch self {
        case .scale: ("0 = gar nicht", "10 = unerträglich")
        case .scaleInverted: ("0 = sehr schlecht", "10 = sehr gut")
        case .binary, .text: nil
        }
    }
}
