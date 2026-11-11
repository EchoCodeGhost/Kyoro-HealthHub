// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 Kyoro-HealthHub contributors
//
// Shared frame for every guided flow (onboarding, test protocols, doctor visit).
// Guarantees the same behaviour everywhere: visible progress, back, an optional
// close button, and one primary action per step. Resuming a paused flow with its
// input is not implemented yet (see tasks.md).

import SwiftUI

struct WizardStep: Identifiable {
    let id: String
    let title: LocalizedStringKey
    let explanation: LocalizedStringKey
    var primaryTitle: LocalizedStringKey = "Weiter"
    /// Steps the user may skip, e.g. optional permissions. Skipping is never penalised.
    var isSkippable = false
}

struct WizardScaffold<StepContent: View>: View {
    let steps: [WizardStep]
    @Binding var currentIndex: Int
    var onFinish: () -> Void
    var onClose: (() -> Void)?
    var onSkip: ((WizardStep) -> Void)?
    @ViewBuilder var content: (WizardStep) -> StepContent
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    private var step: WizardStep { steps[currentIndex] }
    private var isLast: Bool { currentIndex == steps.count - 1 }

    var body: some View {
        VStack(alignment: .leading, spacing: KyoroTheme.Space.l) {
            ProgressView(value: Double(currentIndex + 1), total: Double(steps.count))
                .tint(KyoroTheme.Tint.primary)
                .accessibilityLabel(Text("Schritt \(currentIndex + 1) von \(steps.count)"))

            // Scrolls so long steps (module choice) and the largest text sizes fit;
            // the primary action below stays in reach.
            ScrollView {
                VStack(alignment: .leading, spacing: KyoroTheme.Space.l) {
                    VStack(alignment: .leading, spacing: KyoroTheme.Space.s) {
                        Text(step.title)
                            .font(.title2.bold())
                            .accessibilityAddTraits(.isHeader)
                        Text(step.explanation)
                            .font(.body)
                            .foregroundStyle(.secondary)
                    }
                    content(step)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
            }
            .scrollBounceBehavior(.basedOnSize)

            VStack(spacing: KyoroTheme.Space.s) {
                PrimaryActionButton(title: isLast ? "Fertig" : step.primaryTitle) {
                    advance()
                }
                if step.isSkippable {
                    Button("Überspringen") {
                        onSkip?(step)
                        advance()
                    }
                    .frame(maxWidth: .infinity)
                }
            }
        }
        .padding(KyoroTheme.Space.m)
        .toolbar {
            if currentIndex > 0 {
                ToolbarItem(placement: .topBarLeading) {
                    Button("Zurück", systemImage: "chevron.backward") {
                        withAnimation(reduceMotion ? nil : .default) { currentIndex -= 1 }
                    }
                }
            }
            if let onClose {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Schließen", action: onClose)
                }
            }
        }
        .animation(reduceMotion ? nil : .default, value: currentIndex)
    }

    private func advance() {
        if isLast {
            onFinish()
        } else {
            currentIndex += 1
        }
    }
}
