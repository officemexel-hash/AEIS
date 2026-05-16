package sylion.aeis.operator.push

import io.ktor.client.HttpClient
import io.ktor.client.plugins.contentnegotiation.ContentNegotiation
import io.ktor.client.request.post
import io.ktor.client.request.setBody
import io.ktor.http.ContentType
import io.ktor.http.contentType
import io.ktor.serialization.kotlinx.json.json
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json

@Serializable
private data class PushRegisterRequest(val deviceToken: String, val platform: String)

@Serializable
private data class PushUnregisterRequest(val deviceToken: String)

class PushRepository(
    private val baseUrl: String = "http://localhost:8421",
) : PushService {

    private val httpClient = HttpClient {
        install(ContentNegotiation) {
            json(Json { ignoreUnknownKeys = true })
        }
    }

    override suspend fun registerToken(deviceToken: String, platform: String) {
        try {
            httpClient.post("$baseUrl/api/v1/mobile/push/register") {
                contentType(ContentType.Application.Json)
                setBody(PushRegisterRequest(deviceToken = deviceToken, platform = platform))
            }
        } catch (_: Exception) {
            // Push registration is best-effort — silent on network failure
        }
    }

    override suspend fun unregisterToken(deviceToken: String) {
        try {
            httpClient.post("$baseUrl/api/v1/mobile/push/unregister") {
                contentType(ContentType.Application.Json)
                setBody(PushUnregisterRequest(deviceToken = deviceToken))
            }
        } catch (_: Exception) {
            // Best-effort
        }
    }
}
