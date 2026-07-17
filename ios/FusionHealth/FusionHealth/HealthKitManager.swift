import Foundation
import HealthKit

@MainActor
final class HealthKitManager: ObservableObject {
    private let store = HKHealthStore()
    private var observerQueries: [HKObserverQuery] = []
    @Published private(set) var healthDataChangeID = UUID()

    private var readTypes: Set<HKObjectType> {
        Set([
            HKObjectType.quantityType(forIdentifier: .stepCount)!,
            HKObjectType.quantityType(forIdentifier: .heartRate)!,
            HKObjectType.quantityType(forIdentifier: .activeEnergyBurned)!,
            HKObjectType.quantityType(forIdentifier: .bodyMass)!,
            HKObjectType.categoryType(forIdentifier: .sleepAnalysis)!,
            HKObjectType.workoutType()
        ])
    }

    func requestAuthorization() async throws {
        guard HKHealthStore.isHealthDataAvailable() else {
            throw FusionHealthError.healthKitUnavailable
        }

        try await store.requestAuthorization(toShare: [], read: readTypes)
    }

    func startObservingHealthChanges() {
        guard observerQueries.isEmpty else { return }

        observerQueries = readTypes.compactMap { objectType in
            guard let sampleType = objectType as? HKSampleType else { return nil }
            let query = HKObserverQuery(sampleType: sampleType, predicate: nil) { [weak self] _, completion, error in
                defer { completion() }
                guard error == nil else { return }

                Task { @MainActor [weak self] in
                    self?.healthDataChangeID = UUID()
                }
            }
            store.execute(query)
            return query
        }
    }

    func exportPayload(days: Int) async throws -> AppleHealthImportPayload {
        let start = Calendar.current.date(byAdding: .day, value: -days, to: Date()) ?? Date()
        let end = Date()

        async let steps = fetchDailySteps(start: start, end: end)
        async let sleep = fetchSleep(start: start, end: end)
        async let heartRate = fetchHeartRate(start: start, end: end)
        async let workouts = fetchWorkouts(start: start, end: end)
        async let calories = fetchCalories(start: start, end: end)
        async let bodyMetrics = fetchBodyMass(start: start, end: end)

        return try await AppleHealthImportPayload(
            steps: steps,
            sleep: sleep,
            heartRate: heartRate,
            workouts: workouts,
            calories: calories,
            bodyMetrics: bodyMetrics
        )
    }

    private func fetchDailySteps(start: Date, end: Date) async throws -> [StepSample] {
        guard let type = HKQuantityType.quantityType(forIdentifier: .stepCount) else { return [] }
        let interval = DateComponents(day: 1)
        let anchor = Calendar.current.startOfDay(for: start)
        let predicate = HKQuery.predicateForSamples(withStart: start, end: end)

        return try await withCheckedThrowingContinuation { continuation in
            let query = HKStatisticsCollectionQuery(
                quantityType: type,
                quantitySamplePredicate: predicate,
                options: .cumulativeSum,
                anchorDate: anchor,
                intervalComponents: interval
            )
            query.initialResultsHandler = { _, collection, error in
                if let error {
                    continuation.resume(throwing: error)
                    return
                }

                var rows: [StepSample] = []
                collection?.enumerateStatistics(from: start, to: end) { stats, _ in
                    let count = Int(stats.sumQuantity()?.doubleValue(for: .count()) ?? 0)
                    if count > 0 {
                        rows.append(StepSample(date: Self.dayString(stats.startDate), count: count))
                    }
                }
                continuation.resume(returning: rows)
            }
            store.execute(query)
        }
    }

    private func fetchSleep(start: Date, end: Date) async throws -> [SleepSample] {
        guard let type = HKObjectType.categoryType(forIdentifier: .sleepAnalysis) else { return [] }
        let predicate = HKQuery.predicateForSamples(withStart: start, end: end)

        return try await withCheckedThrowingContinuation { continuation in
            let query = HKSampleQuery(sampleType: type, predicate: predicate, limit: HKObjectQueryNoLimit, sortDescriptors: nil) { _, samples, error in
                if let error {
                    continuation.resume(throwing: error)
                    return
                }

                let rows = (samples as? [HKCategorySample] ?? [])
                    .filter { $0.value == HKCategoryValueSleepAnalysis.asleepCore.rawValue || $0.value == HKCategoryValueSleepAnalysis.asleepDeep.rawValue || $0.value == HKCategoryValueSleepAnalysis.asleepREM.rawValue || $0.value == HKCategoryValueSleepAnalysis.asleepUnspecified.rawValue }
                    .map {
                        SleepSample(
                            start: Self.isoString($0.startDate),
                            end: Self.isoString($0.endDate),
                            sleepHours: round($0.endDate.timeIntervalSince($0.startDate) / 36) / 100,
                            sleepScore: nil
                        )
                    }
                continuation.resume(returning: rows)
            }
            store.execute(query)
        }
    }

    private func fetchHeartRate(start: Date, end: Date) async throws -> [HeartRateSample] {
        guard let type = HKQuantityType.quantityType(forIdentifier: .heartRate) else { return [] }
        let predicate = HKQuery.predicateForSamples(withStart: start, end: end)
        let sort = NSSortDescriptor(key: HKSampleSortIdentifierStartDate, ascending: false)

        return try await withCheckedThrowingContinuation { continuation in
            let query = HKSampleQuery(sampleType: type, predicate: predicate, limit: 2000, sortDescriptors: [sort]) { _, samples, error in
                if let error {
                    continuation.resume(throwing: error)
                    return
                }

                let unit = HKUnit.count().unitDivided(by: .minute())
                let rows = (samples as? [HKQuantitySample] ?? []).map {
                    HeartRateSample(
                        sampledAt: Self.isoString($0.startDate),
                        bpm: $0.quantity.doubleValue(for: unit),
                        context: "apple_health"
                    )
                }
                continuation.resume(returning: rows)
            }
            store.execute(query)
        }
    }

    private func fetchWorkouts(start: Date, end: Date) async throws -> [WorkoutSample] {
        let predicate = HKQuery.predicateForSamples(withStart: start, end: end)
        let sort = NSSortDescriptor(key: HKSampleSortIdentifierStartDate, ascending: false)

        return try await withCheckedThrowingContinuation { continuation in
            let query = HKSampleQuery(sampleType: .workoutType(), predicate: predicate, limit: HKObjectQueryNoLimit, sortDescriptors: [sort]) { _, samples, error in
                if let error {
                    continuation.resume(throwing: error)
                    return
                }

                let rows = (samples as? [HKWorkout] ?? []).map {
                    WorkoutSample(
                        activityName: $0.workoutActivityType.displayName,
                        start: Self.isoString($0.startDate),
                        end: Self.isoString($0.endDate),
                        calories: $0.totalEnergyBurned?.doubleValue(for: .kilocalorie()),
                        averageHeartRate: nil
                    )
                }
                continuation.resume(returning: rows)
            }
            store.execute(query)
        }
    }

    private func fetchCalories(start: Date, end: Date) async throws -> [CalorieSample] {
        guard let type = HKQuantityType.quantityType(forIdentifier: .activeEnergyBurned) else { return [] }
        let interval = DateComponents(day: 1)
        let anchor = Calendar.current.startOfDay(for: start)
        let predicate = HKQuery.predicateForSamples(withStart: start, end: end)

        return try await withCheckedThrowingContinuation { continuation in
            let query = HKStatisticsCollectionQuery(
                quantityType: type,
                quantitySamplePredicate: predicate,
                options: .cumulativeSum,
                anchorDate: anchor,
                intervalComponents: interval
            )
            query.initialResultsHandler = { _, collection, error in
                if let error {
                    continuation.resume(throwing: error)
                    return
                }

                var rows: [CalorieSample] = []
                collection?.enumerateStatistics(from: start, to: end) { stats, _ in
                    let kcal = stats.sumQuantity()?.doubleValue(for: .kilocalorie()) ?? 0
                    if kcal > 0 {
                        rows.append(CalorieSample(date: Self.dayString(stats.startDate), calories: kcal))
                    }
                }
                continuation.resume(returning: rows)
            }
            store.execute(query)
        }
    }

    private func fetchBodyMass(start: Date, end: Date) async throws -> [BodyMetricSample] {
        guard let type = HKQuantityType.quantityType(forIdentifier: .bodyMass) else { return [] }
        let predicate = HKQuery.predicateForSamples(withStart: start, end: end)
        let sort = NSSortDescriptor(key: HKSampleSortIdentifierStartDate, ascending: false)

        return try await withCheckedThrowingContinuation { continuation in
            let query = HKSampleQuery(sampleType: type, predicate: predicate, limit: 100, sortDescriptors: [sort]) { _, samples, error in
                if let error {
                    continuation.resume(throwing: error)
                    return
                }

                let rows = (samples as? [HKQuantitySample] ?? []).map {
                    BodyMetricSample(
                        sampledAt: Self.isoString($0.startDate),
                        type: "body_mass",
                        value: $0.quantity.doubleValue(for: .gramUnit(with: .kilo)),
                        unit: "kg"
                    )
                }
                continuation.resume(returning: rows)
            }
            store.execute(query)
        }
    }

    nonisolated private static func isoString(_ date: Date) -> String {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime]
        return formatter.string(from: date)
    }

    nonisolated private static func dayString(_ date: Date) -> String {
        let formatter = DateFormatter()
        formatter.calendar = Calendar(identifier: .gregorian)
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.dateFormat = "yyyy-MM-dd"
        return formatter.string(from: date)
    }
}

private extension HKWorkoutActivityType {
    var displayName: String {
        switch self {
        case .running: return "Run"
        case .walking: return "Walk"
        case .cycling: return "Cycling"
        case .traditionalStrengthTraining: return "Strength Training"
        case .yoga: return "Yoga"
        case .swimming: return "Swimming"
        default: return "Workout"
        }
    }
}
