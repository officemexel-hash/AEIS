package sylion.aeis.operator.android

import android.os.Bundle
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.viewModels
import androidx.fragment.app.FragmentActivity
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import sylion.aeis.operator.android.auth.BiometricAuth
import sylion.aeis.operator.android.auth.EncryptedTokenStore
import sylion.aeis.operator.android.ui.home.HomeScreen
import sylion.aeis.operator.android.ui.login.LoginScreen
import sylion.aeis.operator.android.ui.login.LoginViewModel
import sylion.aeis.operator.android.ui.login.LoginViewModelFactory
import sylion.aeis.operator.android.ui.theme.AEISOperatorTheme

class MainActivity : FragmentActivity() {

    private val tokenStore by lazy { EncryptedTokenStore(this) }
    private val biometricAuth by lazy { BiometricAuth(this) }
    private val loginViewModel: LoginViewModel by viewModels { LoginViewModelFactory(tokenStore) }

    private var showHome by mutableStateOf(false)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        resolveInitialScreen()

        setContent {
            AEISOperatorTheme {
                Surface(color = MaterialTheme.colorScheme.background) {
                    val uiState by loginViewModel.uiState.collectAsState()

                    LaunchedEffect(uiState.isAuthenticated) {
                        if (uiState.isAuthenticated) showHome = true
                    }

                    if (showHome) {
                        HomeScreen(
                            onLogout = {
                                tokenStore.clear()
                                showHome = false
                            }
                        )
                    } else {
                        LoginScreen(viewModel = loginViewModel)
                    }
                }
            }
        }
    }

    private fun resolveInitialScreen() {
        if (!tokenStore.hasValidToken()) {
            showHome = false
            return
        }
        if (biometricAuth.checkAvailability(this) != BiometricAuth.Availability.AVAILABLE) {
            showHome = true
            return
        }
        // Token exists and biometric is available — require biometric unlock
        biometricAuth.authenticate(
            onSuccess = { showHome = true },
            onError = { showHome = false },
            onFallback = { showHome = false },
        )
    }
}
