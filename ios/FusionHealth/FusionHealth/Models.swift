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
