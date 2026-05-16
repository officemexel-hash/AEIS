package sylion.aeis.operator.auth

interface AuthService {
    suspend fun login(email: String, password: String): Result<AuthState.Authenticated>
    suspend fun logout()
    fun getToken(): String?
    fun isAuthenticated(): Boolean
    fun getState(): AuthState
}
