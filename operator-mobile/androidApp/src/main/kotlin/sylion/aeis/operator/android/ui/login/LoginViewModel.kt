package sylion.aeis.operator.android.ui.login

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import sylion.aeis.operator.android.auth.EncryptedTokenStore
import sylion.aeis.operator.auth.AuthRepository

data class LoginUiState(
    val email: String = "",
    val password: String = "",
    val isLoading: Boolean = false,
    val error: String? = null,
    val isAuthenticated: Boolean = false,
)

class LoginViewModel(
    private val tokenStore: EncryptedTokenStore,
    private val authRepository: AuthRepository = AuthRepository(),
) : ViewModel() {

    private val _uiState = MutableStateFlow(LoginUiState())
    val uiState: StateFlow<LoginUiState> = _uiState

    fun onEmailChange(value: String) {
        _uiState.value = _uiState.value.copy(email = value, error = null)
    }

    fun onPasswordChange(value: String) {
        _uiState.value = _uiState.value.copy(password = value, error = null)
    }

    fun login() {
        val state = _uiState.value
        if (state.email.isBlank() || state.password.isBlank()) {
            _uiState.value = state.copy(error = "Podaj adres e-mail i haslo")
            return
        }
        viewModelScope.launch {
            _uiState.value = state.copy(isLoading = true, error = null)
            authRepository.login(state.email, state.password).fold(
                onSuccess = { authenticated ->
                    tokenStore.saveToken(authenticated.token, authenticated.expiresAt)
                    _uiState.value = _uiState.value.copy(isLoading = false, isAuthenticated = true)
                },
                onFailure = { e ->
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        error = "Blad logowania: ${e.message ?: "nieznany blad"}",
                    )
                },
            )
        }
    }
}

class LoginViewModelFactory(
    private val tokenStore: EncryptedTokenStore,
) : ViewModelProvider.Factory {
    @Suppress("UNCHECKED_CAST")
    override fun <T : ViewModel> create(modelClass: Class<T>): T =
        LoginViewModel(tokenStore) as T
}
