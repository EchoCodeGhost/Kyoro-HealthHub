// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 Kyoro-HealthHub contributors

import UserNotifications

enum ReminderScheduler {
    private static let identifier = "daily-log-reminder"

    /// Schedules one repeating local notification. Nothing leaves the device.
    static func scheduleDaily(hour: Int, minute: Int) async {
        let center = UNUserNotificationCenter.current()
        guard (try? await center.requestAuthorization(options: [.alert, .sound])) == true else { return }

        let content = UNMutableNotificationContent()
        content.title = "Wie geht es dir heute?"
        content.body = "Ein kurzer Eintrag reicht, auch wenn alles in Ordnung ist."

        let trigger = UNCalendarNotificationTrigger(
            dateMatching: DateComponents(hour: hour, minute: minute),
            repeats: true
        )
        center.removePendingNotificationRequests(withIdentifiers: [identifier])
        try? await center.add(UNNotificationRequest(identifier: identifier, content: content, trigger: trigger))
    }
}
