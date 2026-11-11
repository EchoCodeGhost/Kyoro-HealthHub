// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 Kyoro-HealthHub contributors
//
// One diary entry in a list. Stacks at accessibility text sizes instead of
// truncating, and reads as one sentence in VoiceOver.

import SwiftUI

struct EntryRow: View {
    let entry: SymptomEntry
    @Environment(\.dynamicTypeSize) private var typeSize

    var body: some View {
        let layout = typeSize.isAccessibilitySize
            ? AnyLayout(VStackLayout(alignment: .leading, spacing: KyoroTheme.Space.xs))
            : AnyLayout(HStackLayout(spacing: KyoroTheme.Space.s))
        layout {
            Text(entry.label)
            if !typeSize.isAccessibilitySize { Spacer() }
            Text(entry.valueDescription).foregroundStyle(.secondary)
            Text(entry.timestamp, style: .time).foregroundStyle(.secondary)
        }
        .accessibilityElement(children: .combine)
    }
}
