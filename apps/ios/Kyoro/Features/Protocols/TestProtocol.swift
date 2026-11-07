// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 Kyoro-HealthHub contributors
//
// Guided versions of docs/test_protocols/. The protocol documents stay the
// source of truth; step texts here are condensed from them and must be updated
// when a document changes.

import Foundation

enum TestProtocolID: String, CaseIterable, Sendable {
    case orthostatic
}

struct ProtocolStep: Identifiable, Sendable {
    let id: String
    let title: String
    let instruction: String
    /// Countdown for the step, if it is timed.
    var duration: Duration?
    /// Values the user records at the end of the step.
    var measurements: [String] = []
}

struct TestProtocol: Identifiable, Sendable {
    let id: TestProtocolID
    let title: String
    let purpose: String
    let sourceDocument: String
    let safetyNote: String
    let checklist: [String]
    let steps: [ProtocolStep]
}

extension TestProtocol {
    static let orthostatic = TestProtocol(
        id: .orthostatic,
        title: "Stehtest (Schellong / NASA Lean Test)",
        purpose: "Zeigt, wie Puls und Blutdruck auf Aufstehen reagieren.",
        sourceDocument: "docs/test_protocols/ORTHOSTATIC_TEST_PROTOCOL_DE.md",
        safetyNote: "Nur mit einer Begleitperson durchführen, die bei Schwindel hilft und Werte notiert.",
        checklist: [
            "Morgens, 30 bis 60 Minuten nach dem Aufwachen",
            "2 Stunden kein Koffein und nichts gegessen",
            "4 Stunden kein Sport",
            "Etwa 30 Minuten vorher 500 ml Wasser getrunken",
            "Keine Kompressionsstrümpfe",
            "Brustgurt angelegt, Blutdruckmessgerät bereit",
            "Medikamente nicht eigenmächtig pausiert",
        ],
        steps: [
            ProtocolStep(
                id: "lie",
                title: "Liegen",
                instruction: "Flach hinlegen, ohne Kissen, Beine ausgestreckt. Nicht sprechen, nicht aufs Handy schauen. In der letzten Minute Blutdruck messen.",
                duration: .seconds(10 * 60),
                measurements: ["Puls liegend", "Blutdruck liegend"]
            ),
            ProtocolStep(
                id: "stand",
                title: "Aufstehen und anlehnen",
                instruction: "Ruhig aufstehen, ohne sich mit den Armen abzustoßen. Schulterblätter an die Wand, Fersen 15 bis 20 cm davor.",
                duration: .seconds(10 * 60),
                measurements: [
                    "Stehen 0 min", "Stehen 1 min", "Stehen 2 min", "Stehen 3 min",
                    "Stehen 5 min", "Stehen 7 min", "Stehen 10 min",
                ]
            ),
            ProtocolStep(
                id: "recover",
                title: "Wieder hinlegen",
                instruction: "Hinlegen und nach 2 Minuten den Puls notieren.",
                duration: .seconds(2 * 60),
                measurements: ["Puls nach 2 min Liegen"]
            ),
        ]
    )

    static func protocolFor(_ id: TestProtocolID) -> TestProtocol {
        switch id {
        case .orthostatic: .orthostatic
        }
    }
}
