import SwiftUI
import UIKit

struct ContentView: View {
    @Environment(\.scenePhase) private var scenePhase
    @AppStorage("backendURL") private var backendURL = ""
    @AppStorage("syncDays") private var syncDays = 7
    @AppStorage("lastSyncDate") private var lastSyncDate = 0.0
    @AppStorage("healthPermissionRequested") private var healthPermissionRequested = false
    @AppStorage("selectedTab") private var selectedTab = 0

    @StateObject private var healthKit = HealthKitManager()
    @State private var apiKey = KeychainStore.string(forKey: "apiKey")
    @State private var status = "Ready to sync"
    @State private var statusKind = StatusKind.ready
    @State private var isSyncing = false
    @State private var isAuthorizing = false
    @State private var lastPayload: AppleHealthImportPayload?
    @State private var todaySteps: Int?

    private let fiveMinuteRefresh = Timer.publish(every: 300, on: .main, in: .common).autoconnect()

    var body: some View {
        TabView(selection: $selectedTab) {
            NavigationStack {
                SyncDashboard(
                    status: status,
                    statusKind: statusKind,
                    isSyncing: isSyncing,
                    isConfigured: isConfigured,
                    lastSyncDate: lastSyncDate,
                    lastPayload: lastPayload,
                    todaySteps: todaySteps,
                    syncDays: syncDays,
                    syncAction: { Task { await sync() } }
                )
            }
            .tabItem { Label("Sync", systemImage: "arrow.triangle.2.circlepath") }
            .tag(0)

            NavigationStack {
                APISettingsView(
                    backendURL: $backendURL,
                    apiKey: $apiKey,
                    syncDays: $syncDays
                )
            }
            .tabItem { Label("API", systemImage: "server.rack") }
            .tag(1)

            NavigationStack {
                PermissionsView(
                    permissionRequested: healthPermissionRequested,
                    isAuthorizing: isAuthorizing,
                    authorizeAction: { Task { await authorize() } }
                )
            }
            .tabItem { Label("Permissions", systemImage: "lock.shield") }
            .tag(2)
        }
        .tint(.teal)
        .onChange(of: apiKey) { _, newValue in
            KeychainStore.set(newValue, forKey: "apiKey")
        }
        .onReceive(healthKit.$healthDataChangeID.dropFirst()) { _ in
            Task { await refreshHealthData() }
        }
        .onReceive(fiveMinuteRefresh) { _ in
            Task { await refreshHealthData() }
        }
        .task {
            guard healthPermissionRequested else { return }
            healthKit.startObservingHealthChanges()
            await refreshHealthData()
        }
        .onChange(of: scenePhase) { _, newPhase in
            guard newPhase == .active, healthPermissionRequested else { return }
            healthKit.startObservingHealthChanges()
            Task { await refreshHealthData() }
        }
    }

    private var isConfigured: Bool {
        !backendURL.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
            && !apiKey.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
    }

    private func authorize() async {
        isAuthorizing = true
        defer { isAuthorizing = false }

        do {
            try await healthKit.requestAuthorization()
            healthKit.startObservingHealthChanges()
            healthPermissionRequested = true
            status = "Health access request completed"
            statusKind = .success
        } catch {
            status = error.localizedDescription
            statusKind = .error
        }
    }

    private func sync() async {
        isSyncing = true
        status = "Reading Apple Health data…"
        statusKind = .working
        var readSampleCount = 0
        defer { isSyncing = false }

        do {
            try await healthKit.requestAuthorization()
            healthKit.startObservingHealthChanges()
            healthPermissionRequested = true
            let payload = try await healthKit.exportPayload(days: syncDays)
            todaySteps = try await healthKit.fetchTodaySteps()
            lastPayload = payload

            let sampleCount = payload.sampleCount
            readSampleCount = sampleCount
            guard sampleCount > 0 else {
                status = "No Health data found. Review Health access in Permissions."
                statusKind = .warning
                return
            }

            guard isConfigured else {
                status = "Read \(sampleCount) Health samples on this iPhone. Add API settings to upload."
                statusKind = .success
                return
            }

            status = "Uploading securely…"
            let response = try await FusionHealthAPI(baseURL: backendURL, apiKey: apiKey)
                .uploadAppleHealth(payload)
            lastSyncDate = Date().timeIntervalSince1970
            status = "Uploaded \(sampleCount) samples to \(response.provider)"
            statusKind = .success
        } catch {
            if readSampleCount > 0 {
                status = "Read \(readSampleCount) Health samples, but upload failed: \(error.localizedDescription)"
            } else {
                status = error.localizedDescription
            }
            statusKind = .error
        }
    }

    private func refreshHealthData() async {
        guard !isSyncing, healthPermissionRequested else { return }

        do {
            let payload = try await healthKit.exportPayload(days: syncDays)
            todaySteps = try await healthKit.fetchTodaySteps()
            lastPayload = payload
            status = payload.sampleCount > 0
                ? "Updated live from Apple Health"
                : "No Health data found. Review Health access in Permissions."
            statusKind = payload.sampleCount > 0 ? .success : .warning
        } catch {
            status = "Live update failed: \(error.localizedDescription)"
            statusKind = .error
        }
    }
}

private struct SyncDashboard: View {
    let status: String
    let statusKind: StatusKind
    let isSyncing: Bool
    let isConfigured: Bool
    let lastSyncDate: Double
    let lastPayload: AppleHealthImportPayload?
    let todaySteps: Int?
    let syncDays: Int
    let syncAction: () -> Void

    var body: some View {
        ScrollView {
            VStack(spacing: 20) {
                hero
                statusCard
                metrics
            }
            .padding()
        }
        .background(Color(.systemGroupedBackground))
        .navigationTitle("Fusion Health")
    }

    private var hero: some View {
        VStack(alignment: .leading, spacing: 18) {
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: 6) {
                    Text("Apple Health Sync")
                        .font(.title2.bold())
                    Text("Keep your health timeline up to date with one private, on-device sync.")
                        .font(.subheadline)
                        .foregroundStyle(.white.opacity(0.82))
                }
                Spacer()
                Image(systemName: "heart.text.clipboard")
                    .font(.system(size: 34, weight: .semibold))
                    .symbolRenderingMode(.hierarchical)
            }

            Button(action: syncAction) {
                HStack {
                    if isSyncing {
                        ProgressView().tint(.teal)
                    } else {
                        Image(systemName: "arrow.triangle.2.circlepath")
                    }
                    Text(isSyncing ? "Syncing…" : "Sync last \(syncDays) days")
                        .fontWeight(.semibold)
                    Spacer()
                    if !isSyncing { Image(systemName: "arrow.right") }
                }
                .foregroundStyle(.teal)
                .padding(.horizontal, 16)
                .frame(height: 52)
                .background(.white, in: RoundedRectangle(cornerRadius: 15))
            }
            .disabled(isSyncing)
        }
        .foregroundStyle(.white)
        .padding(22)
        .background(
            LinearGradient(
                colors: [Color(red: 0.02, green: 0.42, blue: 0.46), .teal],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            ),
            in: RoundedRectangle(cornerRadius: 24)
        )
        .shadow(color: .teal.opacity(0.2), radius: 18, y: 8)
    }

    private var statusCard: some View {
        VStack(alignment: .leading, spacing: 14) {
            Label("Sync Status", systemImage: "waveform.path.ecg")
                .font(.headline)
            HStack(spacing: 12) {
                Image(systemName: statusKind.icon)
                    .font(.title2)
                    .foregroundStyle(statusKind.color)
                    .symbolEffect(.pulse, isActive: isSyncing)
                VStack(alignment: .leading, spacing: 3) {
                    Text(status).fontWeight(.semibold)
                    if lastSyncDate > 0 {
                        Text("Last synced \(Date(timeIntervalSince1970: lastSyncDate), style: .relative)")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    } else {
                        Text(isConfigured ? "Your first sync is ready" : "Complete API settings to begin")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }
                Spacer()
            }
        }
        .cardStyle()
    }

    @ViewBuilder
    private var metrics: some View {
        if let lastPayload {
            VStack(alignment: .leading, spacing: 14) {
                Text("Latest Health Data").font(.headline)
                LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 12) {
                    MetricTile(title: "Steps Today", value: (todaySteps ?? lastPayload.todaySteps).formatted(), icon: "figure.walk", color: .blue)
                    MetricTile(title: "Sleep", value: String(format: "%.1f h", lastPayload.totalSleepHours), icon: "moon.zzz.fill", color: .indigo)
                    MetricTile(title: "Avg Heart Rate", value: lastPayload.averageHeartRate.map { "\(Int($0.rounded())) bpm" } ?? "—", icon: "heart.fill", color: .pink)
                    MetricTile(title: "Workouts", value: lastPayload.workouts.count.formatted(), icon: "figure.run", color: .orange)
                    MetricTile(title: "Active Energy", value: "\(Int(lastPayload.totalCalories.rounded()).formatted()) kcal", icon: "flame.fill", color: .red)
                    MetricTile(title: "Latest Weight", value: lastPayload.latestBodyMass.map { String(format: "%.1f kg", $0) } ?? "—", icon: "scalemass.fill", color: .green)
                }
            }
        } else {
            ContentUnavailableView(
                "No sync history",
                systemImage: "chart.xyaxis.line",
                description: Text("Your latest upload summary will appear here.")
            )
            .frame(maxWidth: .infinity)
            .padding(.vertical, 22)
            .cardStyle()
        }
    }
}

private struct APISettingsView: View {
    @Binding var backendURL: String
    @Binding var apiKey: String
    @Binding var syncDays: Int
    @State private var revealAPIKey = false

    var body: some View {
        Form {
            Section {
                Label("Your API key is stored in this device's Keychain.", systemImage: "key.horizontal.fill")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            }

            Section("Server") {
                TextField("https://health.example.com", text: $backendURL)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                    .keyboardType(.URL)
                    .textContentType(.URL)

                if backendURL.lowercased().hasPrefix("http://") {
                    Label("Use HTTP only on a trusted local network.", systemImage: "exclamationmark.shield.fill")
                        .font(.footnote)
                        .foregroundStyle(.orange)
                }
            }

            Section("Authentication") {
                HStack {
                    Group {
                        if revealAPIKey {
                            TextField("fh_…", text: $apiKey)
                        } else {
                            SecureField("fh_…", text: $apiKey)
                        }
                    }
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                    .textContentType(.password)

                    Button {
                        revealAPIKey.toggle()
                    } label: {
                        Image(systemName: revealAPIKey ? "eye.slash" : "eye")
                    }
                    .buttonStyle(.plain)
                    .accessibilityLabel(revealAPIKey ? "Hide API key" : "Show API key")
                }
            }

            Section("Documentation") {
                NavigationLink {
                    APIDocumentationView()
                } label: {
                    Label("Fusion Health API Reference", systemImage: "doc.text.magnifyingglass")
                }
            }

            Section {
                Stepper(value: $syncDays, in: 1...30) {
                    LabeledContent("Health history", value: "\(syncDays) days")
                }
            } header: {
                Text("Sync Range")
            } footer: {
                Text("Larger ranges may take longer and upload more samples.")
            }
        }
        .navigationTitle("API Settings")
    }
}

private struct APIDocumentationView: View {
    private let documentURL = Bundle.main.url(forResource: "API_DOCUMENTATION", withExtension: "md")

    var body: some View {
        ScrollView {
            if let attributedDocument {
                Text(attributedDocument)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .textSelection(.enabled)
                    .padding()
            } else {
                ContentUnavailableView(
                    "Documentation unavailable",
                    systemImage: "doc.badge.ellipsis",
                    description: Text("The bundled API reference could not be loaded.")
                )
                .padding(.top, 80)
            }
        }
        .background(Color(.systemGroupedBackground))
        .navigationTitle("API Reference")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            if let documentURL {
                ShareLink(item: documentURL) {
                    Image(systemName: "square.and.arrow.up")
                }
                .accessibilityLabel("Share API documentation")
            }
        }
    }

    private var attributedDocument: AttributedString? {
        guard let documentURL,
              let markdown = try? String(contentsOf: documentURL, encoding: .utf8) else {
            return nil
        }
        return try? AttributedString(
            markdown: markdown,
            options: .init(interpretedSyntax: .full)
        )
    }
}

private struct PermissionsView: View {
    @Environment(\.openURL) private var openURL
    let permissionRequested: Bool
    let isAuthorizing: Bool
    let authorizeAction: () -> Void

    private let permissions: [(String, String, Color)] = [
        ("Steps & Activity", "figure.walk", .blue),
        ("Heart Rate", "heart.fill", .pink),
        ("Sleep", "moon.zzz.fill", .indigo),
        ("Workouts", "figure.run", .orange),
        ("Active Energy", "flame.fill", .red),
        ("Body Mass", "scalemass.fill", .green)
    ]

    var body: some View {
        List {
            Section {
                VStack(spacing: 14) {
                    Image(systemName: permissionRequested ? "checkmark.shield.fill" : "heart.text.clipboard")
                        .font(.system(size: 48))
                        .foregroundStyle(permissionRequested ? .green : .teal)
                    Text(permissionRequested ? "Health access requested" : "Connect Apple Health")
                        .font(.title3.bold())
                    Text("Fusion Health reads only the categories below and never writes to Apple Health.")
                        .multilineTextAlignment(.center)
                        .font(.subheadline)
                        .foregroundStyle(.secondary)

                    Button(action: authorizeAction) {
                        HStack {
                            if isAuthorizing { ProgressView() }
                            Text(permissionRequested ? "Review Health Access" : "Allow Health Access")
                                .fontWeight(.semibold)
                        }
                        .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.borderedProminent)
                    .controlSize(.large)
                    .disabled(isAuthorizing)
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 18)
            }

            Section("Data requested") {
                ForEach(permissions, id: \.0) { permission in
                    Label {
                        Text(permission.0)
                    } icon: {
                        Image(systemName: permission.1)
                            .foregroundStyle(permission.2)
                    }
                }
            }

            Section("Privacy") {
                Label("Data is read on-device", systemImage: "iphone.and.arrow.forward")
                Label("Uploads go only to your configured server", systemImage: "lock.icloud.fill")
                Button("Open System Settings") {
                    if let url = URL(string: UIApplication.openSettingsURLString) {
                        openURL(url)
                    }
                }
            }
        }
        .navigationTitle("Permissions")
    }
}

private struct MetricTile: View {
    let title: String
    let value: String
    let icon: String
    let color: Color

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: icon)
                .frame(width: 34, height: 34)
                .foregroundStyle(color)
                .background(color.opacity(0.12), in: RoundedRectangle(cornerRadius: 10))
            VStack(alignment: .leading, spacing: 2) {
                Text(value).font(.headline)
                Text(title).font(.caption).foregroundStyle(.secondary)
            }
            Spacer(minLength: 0)
        }
        .padding(12)
        .background(Color(.secondarySystemGroupedBackground), in: RoundedRectangle(cornerRadius: 16))
    }
}

private enum StatusKind {
    case ready, working, success, warning, error

    var icon: String {
        switch self {
        case .ready: "circle.dotted"
        case .working: "arrow.triangle.2.circlepath"
        case .success: "checkmark.circle.fill"
        case .warning: "exclamationmark.triangle.fill"
        case .error: "xmark.circle.fill"
        }
    }

    var color: Color {
        switch self {
        case .ready: .secondary
        case .working: .teal
        case .success: .green
        case .warning: .orange
        case .error: .red
        }
    }
}

private extension View {
    func cardStyle() -> some View {
        padding(18)
            .background(Color(.secondarySystemGroupedBackground), in: RoundedRectangle(cornerRadius: 20))
    }
}

#Preview {
    ContentView()
}
