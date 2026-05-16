package sylion.aeis.operator.auth

sealed class AuthState {
    data object Anonymous : AuthState()
    data class Authenticated(
        val token: String,
        val expiresAt: Long,
    ) : AuthState()
}
