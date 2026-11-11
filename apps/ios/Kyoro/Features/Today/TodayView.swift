// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 Kyoro-HealthHub contributors

import SwiftData
import SwiftUI

struct TodayView: View {
    @Binding var selection: AppTab
    @Query private var setups: [UserSetup]
    @Query(sort: \SymptomEntry.timestamp, order: .reverse) private var entries: [SymptomEntry]
    @State private var activeProtocol: TestProtocol?

    private var suggestions: [Suggestion] {
        let setup = setups.first
        let context = SuggestionContext(
            now: .now,
            focusAreas: Set((setup?.focusAreas ?? []).compactMap(Focus.init(rawValue:))),
            healthKitRequested: setup?.healthKitRequested ?? false,
            hubPaired: setup?.hubPaired ?? false,
            lastSymptomLog: entries.first?.timestamp,
            undeliveredEntries: entries.count(where: { $0.deliveredAt == nil })
        )
        return SuggestionEngine.suggestions(for: context)
    }

    private var todaysEntries: [SymptomEntry] {
        entries.filter { Calendar.current.isDateInToday($0.timestamp) }
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: KyoroTheme.Space.l) {
                    if SymptomCatalog.shared.needsCrisisNotice(active: setups.first?.activeModules ?? []) {
                        CrisisNotice()
                    }
                    ForEach(suggestions) { suggestion in
                        SuggestionCard(suggestion: suggestion) { perform(suggestion.action) }
                    }
                    todaySection
                }
                .padding(KyoroTheme.Space.m)
            }
            .navigationTitle("Heute")
            .sheet(item: $activeProtocol) { item in
                ProtocolWizardView(testProtocol: item)
            }
        }
    }

    @ViewBuilder
    private var todaySection: some View {
        VStack(alignment: .leading, spacing: KyoroTheme.Space.s) {
            Text("Heute erfasst").font(.headline)
            if todaysEntries.isEmpty {
                Text("Noch nichts. Über „Erfassen“ oder das Widget geht es in zwei Tipps.")
                    .foregroundStyle(.secondary)
            } else {
                ForEach(todaysEntries) { entry in
                    HStack {
                        Text(entry.label)
                        Spacer()
                        Text(entry.valueDescription).foregroundStyle(.secondary)
                        Text(entry.timestamp, style: .time).foregroundStyle(.secondary)
                    }
                }
            }
        }
    }

    private func perform(_ action: Suggestion.Action) {
        switch action {
        case .logSymptom: selection = .capture
        case .connectHealth, .pairHub, .runAutopilot: selection = .more
        case .startProtocol(let id): activeProtocol = .protocolFor(id)
        }
    }
}

struct SuggestionCard: View {
    let suggestion: Suggestion
    let action: () -> Void

    var body: some View {
        KyoroCard {
            Label(suggestion.title, systemImage: suggestion.systemImage)
                .font(.headline)
            Text(suggestion.reason)
                .font(.subheadline)
                .foregroundStyle(.secondary)
            Button(suggestion.actionTitle, action: action)
                .buttonStyle(.bordered)
                .tint(KyoroTheme.Tint.primary)
                .padding(.top, KyoroTheme.Space.xs)
        }
    }
}
