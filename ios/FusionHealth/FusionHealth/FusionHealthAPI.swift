import Foundation

struct FusionHealthAPI {
    let baseURL: String
    let apiKey: String

    func uploadAppleHealth(_ payload: AppleHealthImportPayload) async throws -> AppleHealthImportResponse {
        guard let url = URL(string: baseURL.trimmingCharacters(in: CharacterSet(charactersIn: "/")) + "/api/v1/import/apple-health") else {
            throw FusionHealthError.invalidBackendURL
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue(apiKey, forHTTPHeaderField: "X-API-Key")
        request.httpBody = try JSONEncoder.fusionHealth.encode(payload)

        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw FusionHealthError.invalidResponse
        }
        guard (200..<300).contains(http.statusCode) else {
            let message = String(data: data, encoding: .utf8) ?? "HTTP \(http.statusCode)"
            throw FusionHealthError.apiError(message)
        }

        return try JSONDecoder.fusionHealth.decode(AppleHealthImportResponse.self, from: data)
    }
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
