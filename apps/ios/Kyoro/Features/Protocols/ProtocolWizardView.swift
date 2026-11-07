// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 Kyoro-HealthHub contributors
//
// Turns a test protocol into a guided flow: checklist first, then one step per
// screen with a countdown and the values to note. Recorded values are not yet
// stored; that comes with the matching importer (see tasks.md).

import SwiftUI

struct ProtocolWizardView: View {
    let testProtocol: TestProtocol
    @Environment(\.dismiss) private var dismiss
    @State private var index = 0
    @State private var checked: Set<String> = []

    private var wizardSteps: [WizardStep] {
        [WizardStep(
            id: "prepare",
            title: "Vorbereitung",
            explanation: LocalizedStringKey(testProtocol.safetyNote),
            primaryTitle: "Alles erledigt"
        )] + testProtocol.steps.map {
            WizardStep(id: $0.id, title: LocalizedStringKey($0.title), explanation: LocalizedStringKey($0.instruction))
        }
    }

    var body: some View {
        NavigationStack {
            WizardScaffold(
                steps: wizardSteps,
                currentIndex: $index,
                onFinish: { dismiss() },
                onClose: { dismiss() }
            ) { step in
                if step.id == "prepare" {
                    checklist
                } else if let protocolStep = testProtocol.steps.first(where: { $0.id == step.id }) {
                    StepTimerView(step: protocolStep)
                }
            }
            .navigationTitle(testProtocol.title)
            .navigationBarTitleDisplayMode(.inline)
        }
    }

    private var checklist: some View {
        VStack(alignment: .leading, spacing: KyoroTheme.Space.s) {
            ForEach(testProtocol.checklist, id: \.self) { item in
                Button {
                    if checked.contains(item) { checked.remove(item) } else { checked.insert(item) }
                } label: {
                    Label(item, systemImage: checked.contains(item) ? "checkmark.circle.fill" : "circle")
                        .foregroundStyle(checked.contains(item) ? KyoroTheme.Tint.primary : .primary)
                }
                .buttonStyle(.plain)
            }
        }
    }
}

private struct StepTimerView: View {
    let step: ProtocolStep
    @State private var endDate: Date?

    var body: some View {
        VStack(alignment: .leading, spacing: KyoroTheme.Space.l) {
            if let duration = step.duration {
                KyoroCard {
                    if let endDate {
                        Text(timerInterval: .now...endDate, countsDown: true)
                            .font(.system(.largeTitle, design: .rounded).monospacedDigit())
                    } else {
                        Button("Timer starten", systemImage: "timer") {
                            endDate = .now.addingTimeInterval(TimeInterval(duration.components.seconds))
                        }
                        .buttonStyle(.bordered)
                        .tint(KyoroTheme.Tint.primary)
                    }
                }
            }
            if !step.measurements.isEmpty {
                VStack(alignment: .leading, spacing: KyoroTheme.Space.xs) {
                    Text("Notieren").font(.headline)
                    ForEach(step.measurements, id: \.self) { Text($0) }
                }
            }
        }
    }
}
