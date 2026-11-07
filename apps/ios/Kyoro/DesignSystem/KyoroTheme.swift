// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 Kyoro-HealthHub contributors
//
// Single source of truth for colours, spacing, radii and type.
// Colours are taken from the Kyoro logo (octopus mascot). No view may use
// ad-hoc values: if something is missing here, add a token instead.

import SwiftUI

enum KyoroTheme {

    // MARK: Colour (from the logo)

    enum Palette {
        /// Octopus body. Primary accent: main button, selection, progress.
        static let teal = Color(hex: 0x00BEB7)
        /// "KYORO" lettering. Curves and active states on dark backgrounds.
        static let aqua = Color(hex: 0x00E5CC)
        /// Suckers and "SymptomTrack". Secondary accent for capture and symptoms.
        static let magenta = Color(hex: 0xE6339F)
        /// Logo background. Dark surfaces, onboarding, widgets.
        static let deepSea = Color(hex: 0x0C1F35)
        /// Glow outline. Only for success moments, never for regular UI.
        static let lime = Color(hex: 0xD6FA14)
    }

    /// Semantic colours. Views use these, not the palette directly.
    /// Light mode uses darker shades of the logo colours: teal and magenta on
    /// white fail WCAG contrast for text (2.3:1 and 3.9:1).
    enum Tint {
        static let primary = Color(light: 0x00807B, dark: 0x00BEB7)
        /// Text and symbols on a `primary` fill (4.8:1 light, 7.2:1 dark).
        static let onPrimary = Color(light: 0xFFFFFF, dark: 0x0C1F35)
        /// Accents for capture (slider, icons). Not for text on dark backgrounds.
        static let capture = Color(light: 0xB3207A, dark: 0xE6339F)
    }

    // MARK: Layout

    /// 4-point grid. Use only these values for padding and spacing.
    enum Space {
        static let xs: CGFloat = 4
        static let s: CGFloat = 8
        static let m: CGFloat = 16
        static let l: CGFloat = 24
    }

    enum Size {
        /// Minimum height of tappable rows; above the 44 pt HIG minimum on purpose.
        static let row: CGFloat = 56
        static let gridItemMinWidth: CGFloat = 150
    }

    enum Radius {
        static let card: CGFloat = 20
        static let control: CGFloat = 14
    }

    /// No-slop rule: at most this many suggestion cards on the Today screen.
    static let maxVisibleSuggestions = 3
}

// MARK: - Helpers

extension Color {
    init(light: UInt32, dark: UInt32) {
        self.init(uiColor: UIColor { traits in
            UIColor(Color(hex: traits.userInterfaceStyle == .dark ? dark : light))
        })
    }

    init(hex: UInt32, opacity: Double = 1) {
        self.init(
            .sRGB,
            red: Double((hex >> 16) & 0xFF) / 255,
            green: Double((hex >> 8) & 0xFF) / 255,
            blue: Double(hex & 0xFF) / 255,
            opacity: opacity
        )
    }
}
