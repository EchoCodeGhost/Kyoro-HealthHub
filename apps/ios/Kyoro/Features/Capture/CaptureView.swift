// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 Kyoro-HealthHub contributors
//
// Two taps: pick a symptom, confirm the value. The list comes from the shared
// catalogue, limited to the modules the user chose. Recently used symptoms sit
// on top, so the daily routine needs no scrolling or searching.

import SwiftData
import SwiftUI

/// A symptom together with the category it is filed under.
struct SymptomPick: Identifiable, Hashable {
    let symptom: CatalogSymptom
    let category: String
    var id: String { symptom.id }
}

struct CaptureView: View {
    @Query private var setups: [UserSetup]
    @Query(sort: \SymptomEntry.timestamp, order: .reverse) private var entries: [SymptomEntry]
    @State private var selected: SymptomPick?
    @State private var search = ""

    private let catalog = SymptomCatalog.shared
    private var activeModules: [String] { setups.first?.activeModules ?? [] }

    private var sections: [(category: CatalogCategory, symptoms: [CatalogSymptom])] {
        catalog.sections(active: activeModules).compactMap { section in
            let hits = search.isEmpty
                ? section.symptoms
                : section.symptoms.filter { $0.label.localizedStandardContains(search) }
            return hits.isEmpty ? nil : (section.category, hits)
        }
    }

    /// Up to six symptoms used most recently, from any module.
    private var recent: [SymptomPick] {
        var seen = Set<String>()
        var picks: [SymptomPick] = []
        for entry in entries where seen.insert(entry.symptomID).inserted {
            if let symptom = catalog.symptom(id: entry.symptomID) {
                picks.append(SymptomPick(symptom: symptom, category: entry.category))
            }
            if picks.count == 6 { break }
        }
        return picks
    }

    var body: some View {
        NavigationStack {
            List {
                if catalog.needsCrisisNotice(active: activeModules) {
                    CrisisNotice()
                        .listRowInsets(EdgeInsets())
                        .listRowBackground(Color.clear)
                }
                if search.isEmpty, !recent.isEmpty {
                    Section("Zuletzt") {
                        ForEach(recent) { pick in row(pick.symptom, category: pick.category) }
                    }
                }
                ForEach(sections, id: \.category.id) { section in
                    Section {
                        ForEach(section.symptoms) { symptom in row(symptom, category: section.category.id) }
                    } header: {
                        Label(section.category.label, systemImage: section.category.systemImage)
                    }
                }
                Section {
                    NavigationLink("Module auswählen") { ModuleSettingsView() }
                } footer: {
                    Text("Hier legst du fest, welche Bereiche in dieser Liste stehen.")
                }
            }
            .searchable(text: $search, prompt: "Symptom suchen")
            .navigationTitle("Erfassen")
            .sheet(item: $selected) { pick in
                EntrySheet(pick: pick) { refreshPinned() }
                    .presentationDetents([.medium, .large])
            }
        }
    }

    private func row(_ symptom: CatalogSymptom, category: String) -> some View {
        Button {
            selected = SymptomPick(symptom: symptom, category: category)
        } label: {
            HStack {
                Text(symptom.label).foregroundStyle(.primary)
                Spacer()
                Text(symptom.type.shortHint).font(.footnote).foregroundStyle(.secondary)
            }
        }
        .accessibilityHint(symptom.type.accessibilityHint)
    }

    /// Keeps the widget on the user's four most frequent 0-10 symptoms.
    private func refreshPinned() {
        let counts = Dictionary(entries.filter { $0.type == .scale || $0.type == .scaleInverted }.map { ($0.symptomID, 1) }, uniquingKeysWith: +)
        let top = counts.sorted { $0.value > $1.value }.map(\.key)
        if !top.isEmpty { SharedStore.pinnedSymptomIDs = top }
    }
}

private struct EntrySheet: View {
    let pick: SymptomPick
    let onSave: () -> Void
    @Environment(\.modelContext) private var modelContext
    @Environment(\.dismiss) private var dismiss
    @State private var value = 5.0
    @State private var text = ""
    @State private var note = ""
    @State private var when = Date.now

    private var symptom: CatalogSymptom { pick.symptom }

    /// A stray swipe must not throw away an entry; "Abbrechen" still closes.
    private var hasInput: Bool { value != 5 || !text.isEmpty || !note.isEmpty }

    var body: some View {
        NavigationStack {
            Form {
                switch symptom.type {
                case .scale, .scaleInverted:
                    Section {
                        Text("\(Int(value)) von 10")
                            .font(.title2.bold())
                            .contentTransition(.numericText())
                        Slider(value: $value, in: 0...10, step: 1) {
                            Text(symptom.label)
                        }
                        .tint(KyoroTheme.Tint.capture)
                        .accessibilityValue("\(Int(value)) von 10")
                        .accessibilityHint(symptom.type.anchors.map { "\($0.low), \($0.high)" } ?? "")
                        if let anchors = symptom.type.anchors {
                            HStack {
                                Text(anchors.low)
                                Spacer()
                                Text(anchors.high)
                            }
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                        }
                    }
                case .binary:
                    Section {
                        Text("Wird als „ist aufgetreten“ gespeichert.")
                            .foregroundStyle(.secondary)
                    }
                case .text:
                    Section {
                        TextField(symptom.label, text: $text)
                    }
                }
                Section {
                    DatePicker("Zeitpunkt", selection: $when, in: ...Date.now)
                    TextField("Notiz (optional)", text: $note, axis: .vertical)
                }
                Section {
                    PrimaryActionButton(title: "Speichern", action: save)
                        .disabled(symptom.type == .text && trimmed(text) == nil)
                }
                .listRowBackground(Color.clear)
                .listRowInsets(EdgeInsets())
            }
            .navigationTitle(symptom.label)
            .navigationBarTitleDisplayMode(.inline)
            .interactiveDismissDisabled(hasInput)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Abbrechen") { dismiss() }
                }
            }
        }
    }

    private func trimmed(_ string: String) -> String? {
        let t = string.trimmingCharacters(in: .whitespacesAndNewlines)
        return t.isEmpty ? nil : t
    }

    private func save() {
        modelContext.insert(SymptomEntry(
            symptom: symptom,
            category: pick.category,
            value: Int(value),
            text: trimmed(text),
            note: trimmed(note),
            timestamp: when
        ))
        try? modelContext.save()
        onSave()
        dismiss()
    }
}

private extension SymptomEntryType {
    var shortHint: String {
        switch self {
        case .scale, .scaleInverted: "0–10"
        case .binary: "ja"
        case .text: "Text"
        }
    }

    var accessibilityHint: String {
        switch self {
        case .scale, .scaleInverted: "Öffnet die Eingabe von 0 bis 10."
        case .binary: "Öffnet die Eingabe, ein Eintrag bedeutet: ist aufgetreten."
        case .text: "Öffnet ein Textfeld."
        }
    }
}
