import SwiftUI
import shared

// Etap 2 skeleton — real Swift UI screens implemented in Etap 3.
// The `shared` KMP framework is linked via CocoaPods (see Podfile).
// Auth, biometric (LocalAuthentication), and push (UserNotifications / APNs)
// will be wired here in Etap 3.
struct ContentView: View {
    var body: some View {
        VStack(spacing: 16) {
            Text("SYLION Operator")
                .font(.largeTitle)
                .bold()
            Text("iOS — Etap 3")
                .foregroundStyle(.secondary)
        }
        .padding()
    }
}

#Preview {
    ContentView()
}
