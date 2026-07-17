import SwiftUI
import BackgroundTasks
import UIKit

private let dailyRefreshIdentifier = "com.local.fusionhealth.daily-refresh"

final class AppDelegate: NSObject, UIApplicationDelegate {
    func application(
        _ application: UIApplication,
        didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]? = nil
    ) -> Bool {
        BGTaskScheduler.shared.register(forTaskWithIdentifier: dailyRefreshIdentifier, using: nil) { task in
            guard let refreshTask = task as? BGAppRefreshTask else {
                task.setTaskCompleted(success: false)
                return
            }
            self.handleDailyRefresh(refreshTask)
        }
        DailyActivitySync.scheduleNextRefresh()
        return true
    }

    func applicationDidEnterBackground(_ application: UIApplication) {
        DailyActivitySync.scheduleNextRefresh()
    }

    private func handleDailyRefresh(_ task: BGAppRefreshTask) {
        DailyActivitySync.scheduleNextRefresh()
        let work = Task { @MainActor in
            let success = await DailyActivitySync.uploadYesterdayIfNeeded()
            task.setTaskCompleted(success: success)
        }
        task.expirationHandler = { work.cancel() }
    }
}

enum DailyActivitySync {
    private static let lastUploadKey = "lastDailyActivityUpload"
    private static let lastUploadTimeKey = "lastDailyActivityUploadTime"

    static func scheduleNextRefresh() {
        BGTaskScheduler.shared.cancel(taskRequestWithIdentifier: dailyRefreshIdentifier)
        let request = BGAppRefreshTaskRequest(identifier: dailyRefreshIdentifier)
        let tomorrow = Calendar.current.date(byAdding: .day, value: 1, to: Date()) ?? Date()
        let nextMidnight = Calendar.current.startOfDay(for: tomorrow)
        request.earliestBeginDate = Calendar.current.date(byAdding: .minute, value: 5, to: nextMidnight)
        try? BGTaskScheduler.shared.submit(request)
    }

    @MainActor
    @discardableResult
    static func uploadYesterdayIfNeeded() async -> Bool {
        let defaults = UserDefaults.standard
        let yesterday = Calendar.current.date(byAdding: .day, value: -1, to: Date()) ?? Date()
        let dateFormatter = DateFormatter()
        dateFormatter.calendar = Calendar(identifier: .gregorian)
        dateFormatter.locale = Locale(identifier: "en_US_POSIX")
        dateFormatter.dateFormat = "yyyy-MM-dd"
        let day = dateFormatter.string(from: yesterday)

        let lastDay = defaults.string(forKey: lastUploadKey)
        let lastUploadTime = defaults.double(forKey: lastUploadTimeKey)
        if lastDay == day, Date().timeIntervalSince1970 - lastUploadTime < 21_600 {
            return true
        }
        let backendURL = defaults.string(forKey: "backendURL") ?? "https://fusion-health-api-qe6l.onrender.com"
        let apiKey = KeychainStore.string(forKey: "apiKey")
        guard !backendURL.isEmpty, !apiKey.isEmpty else { return false }

        do {
            let healthKit = HealthKitManager()
            try await healthKit.requestAuthorization()
            let payload = try await healthKit.exportPayload(days: 2).activityOnly(for: yesterday)
            guard !payload.steps.isEmpty || !payload.calories.isEmpty else { return false }
            _ = try await FusionHealthAPI(baseURL: backendURL, apiKey: apiKey).uploadAppleHealth(payload)
            defaults.set(day, forKey: lastUploadKey)
            defaults.set(Date().timeIntervalSince1970, forKey: lastUploadTimeKey)
            defaults.set(Date().timeIntervalSince1970, forKey: "lastSyncDate")
            return true
        } catch {
            return false
        }
    }
}

@main
struct FusionHealthApp: App {
    @UIApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate

    var body: some Scene {
        WindowGroup {
            ContentView()
        }
    }
}
