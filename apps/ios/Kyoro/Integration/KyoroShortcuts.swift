// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 Kyoro-HealthHub contributors

import AppIntents

struct KyoroShortcuts: AppShortcutsProvider {
    static var appShortcuts: [AppShortcut] {
        AppShortcut(
            intent: LogSymptomIntent(),
            phrases: [
                "\(\.$symptom) in \(.applicationName) erfassen",
                "Symptom in \(.applicationName) erfassen",
            ],
            shortTitle: "Symptom erfassen",
            systemImageName: "plus.circle"
        )
    }
}
