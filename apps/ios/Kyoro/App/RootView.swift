// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 Kyoro-HealthHub contributors

import SwiftData
import SwiftUI

enum AppTab: Hashable {
    case today, capture, history, doctor, more
}

struct RootView: View {
    @Query private var setups: [UserSetup]
    @State private var selection: AppTab = .today

    private var needsOnboarding: Bool { setups.first?.completedOnboardingAt == nil }

    var body: some View {
        TabView(selection: $selection) {
            Tab("Heute", systemImage: "sun.horizon", value: .today) {
                TodayView(selection: $selection)
            }
            Tab("Erfassen", systemImage: "plus.circle", value: .capture) {
                CaptureView()
            }
            Tab("Verlauf", systemImage: "chart.xyaxis.line", value: .history) {
                HistoryView()
            }
            Tab("Arzt", systemImage: "stethoscope", value: .doctor) {
                DoctorView()
            }
            Tab("Mehr", systemImage: "ellipsis.circle", value: .more) {
                MoreView()
            }
        }
        .tint(KyoroTheme.Tint.primary)
        .fullScreenCover(isPresented: .constant(needsOnboarding)) {
            OnboardingFlow()
        }
    }
}
