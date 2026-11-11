// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 Kyoro-HealthHub contributors
//
// Local entries only for now. Hub analyses (plots, findings) arrive with the bridge.

import SwiftData
import SwiftUI

struct HistoryView: View {
    @Query(sort: \SymptomEntry.timestamp, order: .reverse) private var entries: [SymptomEntry]

    private var days: [(day: Date, entries: [SymptomEntry])] {
        let grouped = Dictionary(grouping: entries) { Calendar.current.startOfDay(for: $0.timestamp) }
        return grouped.keys.sorted(by: >).map { ($0, grouped[$0] ?? []) }
    }

    var body: some View {
        NavigationStack {
            Group {
                if entries.isEmpty {
                    ContentUnavailableView(
                        "Noch kein Verlauf",
                        systemImage: "chart.xyaxis.line",
                        description: Text("Erfasse ein Symptom. Auswertungen von deinem Rechner erscheinen hier, sobald er gekoppelt ist.")
                    )
                } else {
                    List(days, id: \.day) { day in
                        Section(day.day.formatted(date: .complete, time: .omitted)) {
                            ForEach(day.entries) { entry in
                                EntryRow(entry: entry)
                            }
                        }
                    }
                }
            }
            .navigationTitle("Verlauf")
        }
    }
}
