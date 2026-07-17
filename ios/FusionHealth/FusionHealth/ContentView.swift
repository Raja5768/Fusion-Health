import SwiftUI

struct ContentView: View {
    @AppStorage("backendURL") private var backendURL = "http://192.168.1.10:8000"
    @AppStorage("apiKey") private var apiKey = ""
    @AppStorage("syncDays") private var syncDays = 7

    @StateObject private var healthKit = HealthKitManager()
    @State private var status = "Ready"
    @State private var isSyncing = false
    @State private var lastPayload: AppleHealthImportPayload?

    var body: some View {
        NavigationStack {
            Form {
                Section("Fusion Health API") {
                    TextField("Backend URL", text: $backendURL)
                        .textInputAutocapitalization(.never)
                        .keyboardType(.URL)
                    SecureField("API Key", text: $apiKey)
                        .textInputAutocapitalization(.never)
                    Stepper("Sync last \(syncDays) days", value: $syncDays, in: 1...30)
                }

                Section("HealthKit") {
                    Button("Authorize Health Access") {
                        Task { await authorize() }
                    }
                    Button("Sync Apple Health") {
                        Task { await sync() }
                    }
                    .disabled(isSyncing || apiKey.isEmpty)
                }

                Section("Status") {
                    Text(status)
                    if let lastPayload {
                        LabeledContent("Steps", value: "\(lastPayload.steps.count)")
                        LabeledContent("Sleep", value: "\(lastPayload.sleep.count)")
                        LabeledContent("Heart Rate", value: "\(lastPayload.heartRate.count)")
                        LabeledContent("Workouts", value: "\(lastPayload.workouts.count)")
                        LabeledContent("Calories", value: "\(lastPayload.calories.count)")
                        LabeledContent("Body Metrics", value: "\(lastPayload.bodyMetrics.count)")
                    }
                }
            }
            .navigationTitle("Fusion Health")
        }
    }

    private func authorize() async {
        do {
            try await healthKit.requestAuthorization()
            status = "Health access authorized"
        } catch {
            status = error.localizedDescription
        }
    }

    private func sync() async {
        isSyncing = true
        defer { isSyncing = false }

        do {
            let payload = try await healthKit.exportPayload(days: syncDays)
            let response = try await FusionHealthAPI(baseURL: backendURL, apiKey: apiKey).uploadAppleHealth(payload)
            lastPayload = payload
            status = "Uploaded to \(response.provider) at \(response.importedAt)"
        } catch {
            status = error.localizedDescription
        }
    }
}

#Preview {
    ContentView()
}
