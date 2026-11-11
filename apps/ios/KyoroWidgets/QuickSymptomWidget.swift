// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 Kyoro-HealthHub contributors
//
// Interactive widget: log one of the four most used symptoms with a 5 in one tap.
// The exact value can be corrected in the app. The app keeps the four ids in
// SharedStore.pinnedSymptomIDs up to date.

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
    private let defaultValue = 5

    private var symptoms: [CatalogSymptom] {
        let catalog = SymptomCatalog.shared
        let pinned = SharedStore.pinnedSymptomIDs.compactMap(catalog.symptom(id:))
        let fallback = SymptomCatalog.defaultPinnedIDs.compactMap(catalog.symptom(id:))
        return Array((pinned + fallback.filter { !pinned.contains($0) }).prefix(4))
    }

    var body: some View {
        VStack(alignment: .leading, spacing: KyoroTheme.Space.s) {
            Text("Symptom erfassen")
                .font(.caption.weight(.semibold))
                .foregroundStyle(.secondary)
            let items = symptoms
            Grid(horizontalSpacing: KyoroTheme.Space.s, verticalSpacing: KyoroTheme.Space.s) {
                ForEach(Array(stride(from: 0, to: items.count, by: 2)), id: \.self) { row in
                    GridRow {
                        button(items[row])
                        if row + 1 < items.count { button(items[row + 1]) }
                    }
                }
            }
        }
        .environment(\.colorScheme, .dark)
        .containerBackground(KyoroTheme.Palette.deepSea, for: .widget)
    }

    private func button(_ symptom: CatalogSymptom) -> some View {
        Button(intent: LogSymptomIntent(symptom: SymptomAppEntity(symptom), value: defaultValue)) {
            Text(symptom.label)
                .font(.caption)
                .lineLimit(2)
                // White on the tinted fill: magenta text on deep sea is only 4.2:1.
                .foregroundStyle(.white)
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
        .description("Deine vier häufigsten Symptome. Ein Tipp speichert eine 5, in der App lässt sich der Wert anpassen.")
        .supportedFamilies([.systemMedium])
    }
}

@main
struct KyoroWidgetBundle: WidgetBundle {
    var body: some Widget {
        QuickSymptomWidget()
    }
}
