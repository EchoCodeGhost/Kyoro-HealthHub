// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 Kyoro-HealthHub contributors
//
// Six steps, each with an immediate effect. Everything else is offered later as
// a suggestion card when it becomes relevant.

import SwiftData
import SwiftUI

struct OnboardingFlow: View {
    @Environment(\.modelContext) private var modelContext
    @State private var index = 0
    @State private var focus: Set<Focus> = []
    @State private var modules: Set<String> = Set(SymptomCatalog.shared.defaultModules)
    @State private var healthGroups: Set<String> = Set(HealthKitService.groups.map(\.id))
    @State private var reminderEnabled = true
    @State private var reminderTime = Calendar.current.date(from: DateComponents(hour: 20)) ?? .now

    private let steps: [WizardStep] = [
        WizardStep(
            id: "welcome",
            title: "Willkommen bei Kyoro",
            explanation: "Kyoro bringt deine Beschwerden, Messwerte und Gerätedaten auf eine Zeitachse. Deine Daten bleiben auf deinem iPhone und deinem eigenen Rechner.",
            primaryTitle: "Einrichten"
        ),
        WizardStep(
            id: "focus",
            title: "Was ist dir gerade wichtig?",
            explanation: "Danach richten sich die Vorschläge auf „Heute“. Du kannst das jederzeit ändern."
        ),
        WizardStep(
            id: "modules",
            title: "Was möchtest du erfassen?",
            explanation: "Die Grundlagen sind schon ausgewählt. Nimm dazu, was zu dir passt. Unter „Mehr“ kannst du das jederzeit ändern."
        ),
        WizardStep(
            id: "health",
            title: "Welche Daten darf Kyoro lesen?",
            explanation: "Apple fragt am Ende der Einrichtung noch einmal einzeln nach. Was du weglässt, kannst du später freigeben.",
            isSkippable: true
        ),
        WizardStep(
            id: "hub",
            title: "Auswertung auf deinem Rechner",
            explanation: "Die Analysen laufen in Kyoro auf deinem eigenen Rechner. Wenn du ihn koppelst, startet die App Import, Berechnung und Analyse für dich.",
            primaryTitle: "Später koppeln"
        ),
        WizardStep(
            id: "reminder",
            title: "Tägliche Erinnerung",
            explanation: "Ein kurzer Hinweis, falls du an einem Tag noch nichts erfasst hast."
        ),
    ]

    var body: some View {
        NavigationStack {
            WizardScaffold(
                steps: steps,
                currentIndex: $index,
                onFinish: finish,
                onSkip: { step in
                    if step.id == "health" { healthGroups = [] }
                }
            ) { step in
                switch step.id {
                case "welcome": welcome
                case "focus": focusPicker
                case "modules": ModulePicker(selection: $modules)
                case "health": healthPicker
                case "hub": hubInfo
                default: reminderPicker
                }
            }
        }
        .interactiveDismissDisabled()
    }

    // MARK: Steps

    private var welcome: some View {
        Image("KyoroMascot")
            .resizable()
            .scaledToFit()
            .clipShape(.rect(cornerRadius: KyoroTheme.Radius.card))
            .accessibilityLabel("Kyoro, ein freundlicher Oktopus mit Stethoskop")
            .frame(maxWidth: .infinity)
    }

    private var focusPicker: some View {
        VStack(spacing: KyoroTheme.Space.s) {
            ForEach(Focus.allCases) { item in
                SelectableRow(
                    title: item.title,
                    detail: item.detail,
                    systemImage: item.systemImage,
                    isSelected: focus.contains(item)
                ) {
                    toggle(item, in: &focus)
                }
            }
        }
    }

    private var healthPicker: some View {
        VStack(spacing: KyoroTheme.Space.s) {
            ForEach(HealthKitService.groups) { group in
                SelectableRow(
                    title: group.title,
                    detail: group.reason,
                    systemImage: group.systemImage,
                    isSelected: healthGroups.contains(group.id)
                ) {
                    toggle(group.id, in: &healthGroups)
                }
            }
        }
    }

    private var hubInfo: some View {
        KyoroCard {
            Label("Koppeln geht über einen QR-Code, den Kyoro auf deinem Rechner anzeigt.", systemImage: "qrcode")
            Label("Ohne Kopplung kannst du Einträge als Datei in den Inbox-Ordner legen.", systemImage: "folder")
        }
    }

    private var reminderPicker: some View {
        KyoroCard {
            Toggle("Erinnerung", isOn: $reminderEnabled)
            if reminderEnabled {
                DatePicker("Uhrzeit", selection: $reminderTime, displayedComponents: .hourAndMinute)
            }
        }
    }

    // MARK: Actions

    private func toggle<T: Hashable>(_ value: T, in set: inout Set<T>) {
        if set.contains(value) { set.remove(value) } else { set.insert(value) }
    }

    private func finish() {
        let setup = UserSetup()
        setup.focusAreas = focus.map(\.rawValue)
        setup.activeModules = SymptomCatalog.shared.modules.map(\.id).filter(modules.contains)
        setup.healthKitRequested = !healthGroups.isEmpty
        setup.dailyReminderHour = reminderEnabled ? Calendar.current.component(.hour, from: reminderTime) : nil
        setup.completedOnboardingAt = .now
        modelContext.insert(setup)

        let selected = HealthKitService.groups.filter { healthGroups.contains($0.id) }
        let time = Calendar.current.dateComponents([.hour, .minute], from: reminderTime)
        let remind = reminderEnabled
        Task {
            try? await HealthKitService().requestReadAccess(for: selected)
            if remind {
                await ReminderScheduler.scheduleDaily(hour: time.hour ?? 20, minute: time.minute ?? 0)
            }
        }
    }
}

struct SelectableRow: View {
    let title: String
    let detail: String
    let systemImage: String
    let isSelected: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(alignment: .top, spacing: KyoroTheme.Space.m) {
                Image(systemName: systemImage)
                    .font(.title3)
                    .foregroundStyle(KyoroTheme.Tint.primary)
                    .frame(width: KyoroTheme.Space.l)
                VStack(alignment: .leading, spacing: KyoroTheme.Space.xs) {
                    Text(title).font(.headline)
                    Text(detail).font(.subheadline).foregroundStyle(.secondary)
                }
                Spacer(minLength: 0)
                Image(systemName: isSelected ? "checkmark.circle.fill" : "circle")
                    .font(.title3)
                    .foregroundStyle(isSelected ? KyoroTheme.Tint.primary : .secondary)
            }
            .padding(KyoroTheme.Space.m)
            .background(.background.secondary, in: .rect(cornerRadius: KyoroTheme.Radius.control))
        }
        .buttonStyle(.plain)
        .accessibilityAddTraits(isSelected ? .isSelected : [])
    }
}
