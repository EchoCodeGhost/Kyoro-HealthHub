// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 Kyoro-HealthHub contributors
//
// Shown without conditions while a catalogue module with
// `requires_crisis_notice` is active (today: Suizidalität). It never depends on
// what was entered, because the app does not assess entries.

import SwiftUI

struct CrisisNotice: View {
    var body: some View {
        KyoroCard {
            Label("Du musst damit nicht allein sein", systemImage: "phone")
                .font(.headline)
            Text("Wenn du gerade an Suizid denkst, sprich mit jemandem. Rund um die Uhr, kostenlos und anonym:")
                .font(.subheadline)
            Link("TelefonSeelsorge 0800 111 0 111", destination: URL(string: "tel:08001110111")!)
            Link("TelefonSeelsorge 0800 111 0 222", destination: URL(string: "tel:08001110222")!)
            Link("In akuter Gefahr: Notruf 112", destination: URL(string: "tel:112")!)
                .fontWeight(.semibold)
        }
        .accessibilityElement(children: .contain)
    }
}
