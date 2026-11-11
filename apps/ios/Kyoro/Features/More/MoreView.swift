// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 Kyoro-HealthHub contributors

import SwiftData
import SwiftUI
import UniformTypeIdentifiers

struct MoreView: View {
    @Query(sort: \SymptomEntry.timestamp) private var entries: [SymptomEntry]
    @Query private var setups: [UserSetup]
    @State private var healthRequestFailed = false

    var body: some View {
        NavigationStack {
            List {
                Section {
                    StatusBadge(level: .unknown, text: "Kein Rechner gekoppelt")
                    exportLink
                } header: {
                    Text("Dein Kyoro-Rechner")
                } footer: {
                    Text("Die Datei in den Ordner imports/_inbox auf deinem Rechner legen und dort process_inbox.py --import ausführen. Die Kopplung per QR-Code folgt mit der Hub-Bridge.")
                }

                Section("Erfassen") {
                    NavigationLink("Module auswählen") { ModuleSettingsView() }
                }

                Section("Apple Health") {
                    Button("Freigaben anfragen", systemImage: "heart.text.square") {
                        Task { await requestHealth() }
                    }
                    .disabled(!HealthKitService.isAvailable)
                    if healthRequestFailed {
                        Text("Die Anfrage hat nicht geklappt. Freigaben lassen sich auch in der Health-App unter Profil > Apps ändern.")
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                    }
                }

                Section("Datenschutz") {
                    Label("Deine Daten bleiben auf diesem iPhone und deinem eigenen Rechner. Kyoro sendet nichts an Dritte.", systemImage: "lock")
                    Label("Kyoro stellt keine Diagnosen. Hinweise sind Anlass, ärztlich nachzufragen.", systemImage: "cross.case")
                }
            }
            .navigationTitle("Mehr")
        }
    }

    @ViewBuilder
    private var exportLink: some View {
        if entries.isEmpty {
            Text("Noch keine Einträge zum Exportieren.").foregroundStyle(.secondary)
        } else if let data = try? SymptomExport.encode(SymptomExport.makeFile(from: entries)) {
            ShareLink(
                item: ExportedFile(data: data, fileName: SymptomExport.fileName()),
                preview: SharePreview(SymptomExport.fileName())
            ) {
                Label("Einträge als Datei exportieren (\(entries.count))", systemImage: "square.and.arrow.up")
            }
        }
    }

    private func requestHealth() async {
        do {
            try await HealthKitService().requestReadAccess(for: HealthKitService.groups)
            setups.first?.healthKitRequested = true
            healthRequestFailed = false
        } catch {
            healthRequestFailed = true
        }
    }
}

/// Shares the export without writing a temporary file from the view body.
private struct ExportedFile: Transferable {
    let data: Data
    let fileName: String

    static var transferRepresentation: some TransferRepresentation {
        DataRepresentation(exportedContentType: .json) { $0.data }
            .suggestedFileName { $0.fileName }
    }
}
