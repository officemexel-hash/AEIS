package sylion.aeis.operator.auth

import io.ktor.client.HttpClient
import io.ktor.client.call.body
import io.ktor.client.plugins.contentnegotiation.ContentNegotiation
import io.ktor.client.request.post
import io.ktor.client.request.setBody
import io.ktor.http.ContentType
import io.ktor.http.contentType
import io.ktor.serialization.kotlinx.json.json
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json

@Serializable
private data class LoginRequest(val email: String, val password: String)

@Serializable
private data class LoginResponse(val token: String, val expiresAt: Long)

class AuthRepository(
    private val baseUrl: String = "http://localhost:8421",
) : AuthService {

    private var _state: AuthState = AuthState.Anonymous

    private val httpClient = HttpClient {
        install(ContentNegotiation) {
            json(Json { ignoreUnknownKeys = true })
        }
    }

    override suspend fun login(email: String, password: String): Result<AuthState.Authenticated> {
        return try {
            val response: LoginResponse = httpClient
                .post("$baseUrl/api/v1/mobile/auth/login") {
                    contentType(ContentType.Application.Json)
                    setBody(LoginRequest(email = email, password = password))
                }
                .body()
            val authenticated = AuthState.Authenticated(
                token = response.token,
                expiresAt = response.expiresAt,
            )
            _state = authenticated
            Result.success(authenticated)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    override suspend fun logout() {
        _state = AuthState.Anonymous
    }

    override fun getToken(): String? = (_state as? AuthState.Authenticated)?.token

    override fun isAuthenticated(): Boolean = _state is AuthState.Authenticated

    override fun getState(): AuthState = _state
}
