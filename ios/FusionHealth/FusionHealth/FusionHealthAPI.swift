import Foundation

struct FusionHealthAPI {
    let baseURL: String
    let apiKey: String

    func uploadAppleHealth(_ payload: AppleHealthImportPayload) async throws -> AppleHealthImportResponse {
        let normalizedAPIKey = apiKey.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !normalizedAPIKey.isEmpty else {
            throw FusionHealthError.invalidAPIKey
        }

        let normalizedBaseURL = baseURL.trimmingCharacters(in: .whitespacesAndNewlines)
            .trimmingCharacters(in: CharacterSet(charactersIn: "/"))
        guard let base = URL(string: normalizedBaseURL),
              let scheme = base.scheme?.lowercased(),
              ["http", "https"].contains(scheme),
              base.host != nil,
              let url = URL(string: normalizedBaseURL + "/api/v1/import/apple-health") else {
            throw FusionHealthError.invalidBackendURL
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.timeoutInterval = 30
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue(normalizedAPIKey, forHTTPHeaderField: "X-API-Key")
        request.httpBody = try JSONEncoder.fusionHealth.encode(payload)

        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw FusionHealthError.invalidResponse
        }
        guard (200..<300).contains(http.statusCode) else {
            let message = (try? JSONDecoder().decode(APIErrorResponse.self, from: data).detail)
                ?? HTTPURLResponse.localizedString(forStatusCode: http.statusCode)
            throw FusionHealthError.apiError(message)
        }

        return try JSONDecoder.fusionHealth.decode(AppleHealthImportResponse.self, from: data)
    }
}

private struct APIErrorResponse: Decodable {
    let detail: String
}

extension JSONEncoder {
    static var fusionHealth: JSONEncoder {
        let encoder = JSONEncoder()
        encoder.keyEncodingStrategy = .convertToSnakeCase
        return encoder
    }
}

extension JSONDecoder {
    static var fusionHealth: JSONDecoder {
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        return decoder
    }
}
