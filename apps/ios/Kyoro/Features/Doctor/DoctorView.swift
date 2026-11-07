// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 Kyoro-HealthHub contributors
//
// Entry point for "prepare a doctor's visit". The user picks the specialty in
// plain words; the app maps it to an export profile of scripts/export_health.py.

import SwiftUI

struct ExportProfile: Identifiable, Hashable {
    /// Profile name as accepted by export_health.py --profile.
    let id: String
    let specialty: String
}

enum ExportProfiles {
    /// Order: the specialties most people visit first.
    static let all: [ExportProfile] = [
        .init(id: "general_practitioner", specialty: "Hausarzt"),
        .init(id: "cardiology", specialty: "Kardiologie"),
        .init(id: "neurology", specialty: "Neurologie"),
        .init(id: "gynecology", specialty: "Gynäkologie"),
        .init(id: "sleep", specialty: "Schlafmedizin"),
        .init(id: "metabolic", specialty: "Diabetologie und Stoffwechsel"),
        .init(id: "pulmonology", specialty: "Lungenheilkunde"),
        .init(id: "rheumatology", specialty: "Rheumatologie"),
        .init(id: "mental_health", specialty: "Psychiatrie und Psychotherapie"),
        .init(id: "long_covid", specialty: "Long-/Post-COVID-Ambulanz"),
        .init(id: "ent", specialty: "HNO"),
        .init(id: "immunology", specialty: "Immunologie"),
        .init(id: "infectiology", specialty: "Infektiologie"),
        .init(id: "oncology", specialty: "Onkologie"),
        .init(id: "nutrition", specialty: "Ernährungsberatung"),
        .init(id: "sports_medicine", specialty: "Sportmedizin"),
        .init(id: "functional_medicine", specialty: "Funktionelle Medizin"),
        .init(id: "clinical_full", specialty: "Alles (vollständiger Export)"),
    ]
}

struct DoctorView: View {
    @State private var profile: ExportProfile?

    var body: some View {
        NavigationStack {
            List {
                Section {
                    ForEach(ExportProfiles.all) { item in
                        Button(item.specialty) { profile = item }
                    }
                } header: {
                    Text("Zu welchem Termin gehst du?")
                } footer: {
                    Text("Der Export enthält nur deine Messwerte, keine KI-Kommentare.")
                }
            }
            .navigationTitle("Arzt")
            .sheet(item: $profile) { item in
                ExportPlanSheet(profile: item)
                    .presentationDetents([.medium])
            }
        }
    }
}

/// Until the hub bridge exists the app cannot run the export itself, so it hands
/// over the exact command instead of a button that would do nothing.
private struct ExportPlanSheet: View {
    let profile: ExportProfile

    private var command: String {
        "python3 scripts/export_health.py --profile \(profile.id) --last 365d --format csv"
    }

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    Text(command)
                        .font(.footnote.monospaced())
                        .textSelection(.enabled)
                    Button("Befehl kopieren", systemImage: "doc.on.doc") {
                        UIPasteboard.general.string = command
                    }
                } header: {
                    Text("Auf deinem Rechner ausführen")
                } footer: {
                    Text("Sobald dein Rechner gekoppelt ist, startet die App den Export selbst.")
                }
            }
            .navigationTitle(profile.specialty)
            .navigationBarTitleDisplayMode(.inline)
        }
    }
}
