// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 Kyoro-HealthHub contributors

import SwiftUI

/// Content card. Plain surface, no glass: Liquid Glass is reserved for system chrome.
struct KyoroCard<Content: View>: View {
    @ViewBuilder var content: Content

    var body: some View {
        VStack(alignment: .leading, spacing: KyoroTheme.Space.s) {
            content
        }
        .padding(KyoroTheme.Space.m)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(.background.secondary, in: .rect(cornerRadius: KyoroTheme.Radius.card))
    }
}

/// The one prominent action of a screen.
struct PrimaryActionButton: View {
    let title: LocalizedStringKey
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            Text(title)
                .font(.headline)
                .foregroundStyle(KyoroTheme.Tint.onPrimary)
                .frame(maxWidth: .infinity)
                .padding(.vertical, KyoroTheme.Space.xs)
        }
        .buttonStyle(.borderedProminent)
        .buttonBorderShape(.roundedRectangle(radius: KyoroTheme.Radius.control))
        .controlSize(.large)
        .tint(KyoroTheme.Tint.primary)
    }
}

/// Status shown with symbol and text, never colour alone.
struct StatusBadge: View {
    enum Level { case ok, attention, unknown }

    let level: Level
    let text: LocalizedStringKey

    var body: some View {
        Label(text, systemImage: symbol)
            .font(.subheadline.weight(.medium))
            .foregroundStyle(color)
    }

    private var symbol: String {
        switch level {
        case .ok: "checkmark.circle.fill"
        case .attention: "exclamationmark.circle.fill"
        case .unknown: "questionmark.circle"
        }
    }

    private var color: Color {
        switch level {
        case .ok: .green
        case .attention: .orange
        case .unknown: .secondary
        }
    }
}
