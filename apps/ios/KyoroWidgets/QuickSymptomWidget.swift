// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 Kyoro-HealthHub contributors
//
// Interactive widget: log one of four symptoms with medium severity in one tap.
// The exact severity can be corrected in the app.

import AppIntents
import SwiftUI
import WidgetKit

struct QuickSymptomEntry: TimelineEntry {
    let date: Date
}

struct QuickSymptomProvider: TimelineProvider {
    func placeholder(in context: Context) -> QuickSymptomEntry { QuickSymptomEntry(date: .now) }

    func getSnapshot(in context: Context, completion: @escaping (QuickSymptomEntry) -> Void) {
        completion(QuickSymptomEntry(date: .now))
    }

    func getTimeline(in context: Context, completion: @escaping (Timeline<QuickSymptomEntry>) -> Void) {
        // Content does not change over time, so one entry and no reloads.
        completion(Timeline(entries: [QuickSymptomEntry(date: .now)], policy: .never))
    }
}

struct QuickSymptomWidgetView: View {
    private let symptoms = Array(SymptomCatalog.quickPick.prefix(4))
    private let defaultSeverity = 5

    var body: some View {
        VStack(alignment: .leading, spacing: KyoroTheme.Space.s) {
            Text("Symptom erfassen")
                .font(.caption.weight(.semibold))
                .foregroundStyle(.secondary)
            Grid(horizontalSpacing: KyoroTheme.Space.s, verticalSpacing: KyoroTheme.Space.s) {
                GridRow {
                    button(symptoms[0])
                    button(symptoms[1])
                }
                GridRow {
                    button(symptoms[2])
                    button(symptoms[3])
                }
            }
        }
        .environment(\.colorScheme, .dark)
        .containerBackground(KyoroTheme.Palette.deepSea, for: .widget)
    }

    private func button(_ symptom: SymptomDefinition) -> some View {
        Button(intent: LogSymptomIntent(symptom: SymptomAppEntity(symptom), severity: defaultSeverity)) {
            Label(symptom.displayName, systemImage: symptom.systemImage)
                .font(.caption)
                .lineLimit(1)
                .frame(maxWidth: .infinity, alignment: .leading)
        }
        .tint(KyoroTheme.Tint.capture)
    }
}

struct QuickSymptomWidget: Widget {
    var body: some WidgetConfiguration {
        StaticConfiguration(kind: "QuickSymptom", provider: QuickSymptomProvider()) { _ in
            QuickSymptomWidgetView()
        }
        .configurationDisplayName("Symptom erfassen")
        .description("Ein Tipp speichert das Symptom mit Stärke 5. In der App lässt sich die Stärke anpassen.")
        .supportedFamilies([.systemMedium])
    }
}

@main
struct KyoroWidgetBundle: WidgetBundle {
    var body: some Widget {
        QuickSymptomWidget()
    }
}
