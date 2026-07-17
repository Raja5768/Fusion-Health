import Foundation

struct AppleHealthImportPayload: Codable {
    var steps: [StepSample]
    var sleep: [SleepSample]
    var heartRate: [HeartRateSample]
    var workouts: [WorkoutSample]
    var calories: [CalorieSample]
    var bodyMetrics: [BodyMetricSample]

    var sampleCount: Int {
        steps.count + sleep.count + heartRate.count + workouts.count + calories.count + bodyMetrics.count
    }

    var totalSteps: Int {
        steps.reduce(0) { $0 + $1.count }
    }

    var todaySteps: Int {
        let formatter = DateFormatter()
        formatter.calendar = Calendar(identifier: .gregorian)
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.dateFormat = "yyyy-MM-dd"
        let today = formatter.string(from: Date())
        return steps.first(where: { $0.date == today })?.count ?? 0
    }

    var totalSleepHours: Double {
        sleep.reduce(0) { $0 + $1.sleepHours }
    }

    var averageHeartRate: Double? {
        guard !heartRate.isEmpty else { return nil }
        return heartRate.reduce(0) { $0 + $1.bpm } / Double(heartRate.count)
    }

    var totalCalories: Double {
        calories.reduce(0) { $0 + $1.calories }
    }

    var latestBodyMass: Double? {
        bodyMetrics.first(where: { $0.type == "body_mass" })?.value
    }
}

struct StepSample: Codable {
    let date: String
    let count: Int
}

struct SleepSample: Codable {
    let start: String
    let end: String
    let sleepHours: Double
    let sleepScore: Double?
}

struct HeartRateSample: Codable {
    let sampledAt: String
    let bpm: Double
    let context: String?
}

struct WorkoutSample: Codable {
    let activityName: String
    let start: String
    let end: String
    let calories: Double?
    let averageHeartRate: Double?
}

struct CalorieSample: Codable {
    let date: String
    let calories: Double
}

struct BodyMetricSample: Codable {
    let sampledAt: String
    let type: String
    let value: Double
    let unit: String
}

struct AppleHealthImportResponse: Decodable {
    let provider: String
    let imported: [String: Int]
    let importedAt: String
}

enum FusionHealthError: LocalizedError {
    case healthKitUnavailable
    case invalidBackendURL
    case invalidAPIKey
    case invalidResponse
    case apiError(String)

    var errorDescription: String? {
        switch self {
        case .healthKitUnavailable:
            return "HealthKit is unavailable on this device."
        case .invalidBackendURL:
            return "The backend URL is invalid. Enter a complete HTTP or HTTPS URL."
        case .invalidAPIKey:
            return "Enter a valid Fusion Health API key."
        case .invalidResponse:
            return "Fusion Health returned an invalid response."
        case .apiError(let message):
            return message
        }
    }
}
