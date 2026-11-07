// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 Kyoro-HealthHub contributors
//
// Two taps: pick a symptom, confirm the severity. Note is optional.

import SwiftData
import SwiftUI

struct CaptureView: View {
    @State private var selected: SymptomDefinition?

    private let columns = [GridItem(.adaptive(minimum: KyoroTheme.Size.gridItemMinWidth), spacing: KyoroTheme.Space.s)]

    var body: some View {
        NavigationStack {
            ScrollView {
                LazyVGrid(columns: columns, spacing: KyoroTheme.Space.s) {
                    ForEach(SymptomCatalog.quickPick) { symptom in
                        Button { selected = symptom } label: {
                            Label(symptom.displayName, systemImage: symptom.systemImage)
                                .frame(maxWidth: .infinity, minHeight: KyoroTheme.Size.row, alignment: .leading)
                                .padding(.horizontal, KyoroTheme.Space.m)
                                .background(.background.secondary, in: .rect(cornerRadius: KyoroTheme.Radius.control))
                        }
                        .buttonStyle(.plain)
                    }
                }
                .padding(KyoroTheme.Space.m)
            }
            .navigationTitle("Erfassen")
            .sheet(item: $selected) { symptom in
                SeveritySheet(symptom: symptom)
                    .presentationDetents([.medium])
            }
        }
    }
}

private struct SeveritySheet: View {
    let symptom: SymptomDefinition
    @Environment(\.modelContext) private var modelContext
    @Environment(\.dismiss) private var dismiss
    @State private var severity = 5.0
    @State private var note = ""

    var body: some View {
        NavigationStack {
            VStack(alignment: .leading, spacing: KyoroTheme.Space.l) {
                VStack(alignment: .leading, spacing: KyoroTheme.Space.s) {
                    Text("Stärke \(Int(severity))")
                        .font(.title2.bold())
                        .contentTransition(.numericText())
                    Slider(value: $severity, in: 0...10, step: 1) {
                        Text("Stärke")
                    } minimumValueLabel: {
                        Text("0")
                    } maximumValueLabel: {
                        Text("10")
                    }
                    .tint(KyoroTheme.Tint.capture)
                    Text("0 = keine Beschwerden, 10 = stärkste vorstellbare")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }
                TextField("Notiz (optional)", text: $note, axis: .vertical)
                    .textFieldStyle(.roundedBorder)
                Spacer()
                PrimaryActionButton(title: "Speichern") {
                    save()
                }
            }
            .padding(KyoroTheme.Space.m)
            .navigationTitle(symptom.displayName)
            .navigationBarTitleDisplayMode(.inline)
        }
    }

    private func save() {
        let trimmed = note.trimmingCharacters(in: .whitespacesAndNewlines)
        modelContext.insert(SymptomEntry(
            hubKey: symptom.hubKey,
            category: symptom.category,
            severity: Int(severity),
            note: trimmed.isEmpty ? nil : trimmed
        ))
        dismiss()
    }
}
