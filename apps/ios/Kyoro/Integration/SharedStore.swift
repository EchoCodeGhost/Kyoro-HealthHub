// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 Kyoro-HealthHub contributors
//
// Hand-over between the widget extension / Siri and the app. Widgets run in a
// separate process and cannot open the app's SwiftData store safely, so they drop
// quick logs here; the app moves them into SwiftData the next time it is active.

import Foundation

struct QuickLog: Codable, Hashable, Sendable {
    let hubKey: String
    let severity: Int
    let timestamp: Date
}

enum SharedStore {
    static let appGroup = "group.org.kyoro.app"
    private static let pendingKey = "pendingQuickLogs"

    private static var defaults: UserDefaults? { UserDefaults(suiteName: appGroup) }

    static func enqueue(_ log: QuickLog) {
        var logs = pending()
        logs.append(log)
        save(logs)
    }

    static func pending() -> [QuickLog] {
        guard let data = defaults?.data(forKey: pendingKey) else { return [] }
        return (try? JSONDecoder().decode([QuickLog].self, from: data)) ?? []
    }

    /// Returns all pending logs and clears the queue.
    static func drain() -> [QuickLog] {
        let logs = pending()
        save([])
        return logs
    }

    private static func save(_ logs: [QuickLog]) {
        guard let data = try? JSONEncoder().encode(logs) else { return }
        defaults?.set(data, forKey: pendingKey)
    }
}
