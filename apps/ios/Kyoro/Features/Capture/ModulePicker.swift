// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 Kyoro-HealthHub contributors
//
// Choose which catalogue modules appear under "Erfassen". Used in onboarding and
// under "Mehr". The basic modules are preselected; everything else is opt-in.

import SwiftData
import SwiftUI

struct ModulePicker: View {
    @Binding var selection: Set<String>
    private let catalog = SymptomCatalog.shared

    private var basic: [CatalogModule] { catalog.modules.filter { $0.id.hasPrefix("basis_") } }
    private var specific: [CatalogModule] { catalog.modules.filter { !$0.id.hasPrefix("basis_") } }

    var body: some View {
        VStack(alignment: .leading, spacing: KyoroTheme.Space.l) {
            group("Grundlagen", basic)
            group("Bei bestimmten Erkrankungen", specific)
        }
    }

    private func group(_ title: String, _ modules: [CatalogModule]) -> some View {
        VStack(alignment: .leading, spacing: KyoroTheme.Space.s) {
            Text(title).font(.headline)
            ForEach(modules) { module in
                SelectableRow(
                    title: module.label,
                    detail: detail(for: module),
                    systemImage: catalog.category(id: module.category)?.systemImage ?? "circle.grid.2x2",
                    isSelected: selection.contains(module.id)
                ) {
                    if selection.contains(module.id) { selection.remove(module.id) } else { selection.insert(module.id) }
                }
            }
        }
    }

    private func detail(for module: CatalogModule) -> String {
        let count = module.symptoms.count == 1 ? "1 Eintrag" : "\(module.symptoms.count) Einträge"
        if module.requiresCrisisNotice {
            return "\(module.description) \(count). Solange aktiv, zeigt Kyoro dauerhaft Hilfenummern."
        }
        return "\(module.description) \(count)."
    }
}

/// Module choice after onboarding, reachable from "Mehr" and from "Erfassen".
struct ModuleSettingsView: View {
    @Query private var setups: [UserSetup]
    @State private var selection: Set<String> = []

    var body: some View {
        ScrollView {
            ModulePicker(selection: $selection)
                .padding(KyoroTheme.Space.m)
        }
        .navigationTitle("Was du erfasst")
        .onAppear {
            let active = setups.first?.activeModules ?? []
            selection = Set(active.isEmpty ? SymptomCatalog.shared.defaultModules : active)
        }
        .onChange(of: selection) { _, new in
            // Catalogue order keeps the "Erfassen" list stable.
            setups.first?.activeModules = SymptomCatalog.shared.modules.map(\.id).filter(new.contains)
        }
    }
}

extension CatalogCategory {
    /// SF Symbol per catalogue category. Symbols only, no emoji.
    var systemImage: String {
        switch id {
        case "ressourcen": "battery.75percent"
        case "erschoepfung": "bed.double"
        case "sensorisch": "ear"
        case "schmerz": "bolt"
        case "psyche", "psychose": "brain.head.profile"
        case "bauchraum": "fork.knife"
        case "auge": "eye"
        case "erkaeltung": "lungs"
        case "behandlung": "cross.case"
        case "migraene": "brain"
        case "neurodegeneration": "figure.walk"
        case "rheuma", "fibromyalgie": "figure.arms.open"
        case "lipoedem": "figure.stand"
        case "hormonell": "drop"
        case "kreislauf": "heart"
        case "haut": "hand.raised"
        case "borreliose": "ant"
        default: "circle.grid.2x2"
        }
    }
}
