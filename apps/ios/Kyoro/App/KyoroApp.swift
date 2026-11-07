// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 Kyoro-HealthHub contributors

import SwiftData
import SwiftUI

@main
struct KyoroApp: App {
    @Environment(\.scenePhase) private var scenePhase
    private let container: ModelContainer

    init() {
        do {
            container = try ModelContainer(for: SymptomEntry.self, UserSetup.self)
        } catch {
            fatalError("Lokaler Speicher konnte nicht geöffnet werden: \(error)")
        }
    }

    var body: some Scene {
        WindowGroup {
            RootView()
        }
        .modelContainer(container)
        .onChange(of: scenePhase) { _, phase in
            if phase == .active {
                importQuickLogs()
            }
        }
    }

    /// Moves entries logged from the widget or Siri into the app's store.
    @MainActor
    private func importQuickLogs() {
        let context = container.mainContext
        for log in SharedStore.drain() {
            let category = SymptomCatalog.definition(for: log.hubKey)?.category ?? "other"
            context.insert(SymptomEntry(hubKey: log.hubKey, category: category, severity: log.severity, timestamp: log.timestamp))
        }
        try? context.save()
    }
}
