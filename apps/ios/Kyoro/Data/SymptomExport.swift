// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 Kyoro-HealthHub contributors
//
// Writes symptom entries in the format that
// scripts/importers/import_symptomtrack_export.py already reads
// (top-level `symptom_entries[]`, German field names). Reusing that format means
// the hub needs no new importer for phone data.

import Foundation

struct SymptomExportFile: Encodable {
    struct Entry: Encodable {
        let id: String
        let timestamp: String
        let symptom: String
        let kategorie: String
        let wert_num: Int
        let wert_text: String?
        let note: String?
        let source: String
    }

    let exported_at: String
    let symptom_entries: [Entry]
}

enum SymptomExport {
    static let source = "kyoro_ios"

    /// File name pattern the importer documents: symptomtrack_export_YYYY-MM-DD.json
    static func fileName(for date: Date = .now) -> String {
        "symptomtrack_export_\(date.formatted(.iso8601.year().month().day())).json"
    }

    static func makeFile(from entries: [SymptomEntry], now: Date = .now) -> SymptomExportFile {
        let iso = ISO8601DateFormatter()
        return SymptomExportFile(
            exported_at: iso.string(from: now),
            symptom_entries: entries.map { entry in
                .init(
                    id: entry.id.uuidString,
                    timestamp: iso.string(from: entry.timestamp),
                    symptom: entry.hubKey,
                    kategorie: entry.category,
                    wert_num: entry.severity,
                    wert_text: nil,
                    note: entry.note,
                    source: source
                )
            }
        )
    }

    static func encode(_ file: SymptomExportFile) throws -> Data {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        return try encoder.encode(file)
    }
}
