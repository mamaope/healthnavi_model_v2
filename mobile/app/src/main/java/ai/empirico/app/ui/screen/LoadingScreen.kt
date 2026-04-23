package ai.empirico.app.ui.screen

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import ai.empirico.app.ui.theme.TextSecondary
import ai.empirico.app.ui.viewmodel.AuthViewModel
import kotlinx.coroutines.delay

private const val INIT_TIMEOUT_MS = 15_000L

/**
 * Shown on app start until auth is initialized (token restored).
 * Then navigates to Chat (if logged in) or Login.
 * Handles timeout and init errors by redirecting to login.
 */
@Composable
fun LoadingScreen(
    authViewModel: AuthViewModel,
    onNavigateToLogin: () -> Unit,
    onNavigateToChat: () -> Unit
) {
    val state by authViewModel.uiState.collectAsState()
    val isInitialized = state.isInitialized
    val isAuthenticated = state.isAuthenticated
    var timedOut by remember { mutableStateOf(false) }

    // Timeout: if init takes too long (e.g. network down), redirect to login
    LaunchedEffect(Unit) {
        delay(INIT_TIMEOUT_MS)
        if (!authViewModel.uiState.value.isInitialized) {
            timedOut = true
        }
    }

    LaunchedEffect(isInitialized, timedOut) {
        when {
            timedOut -> onNavigateToLogin()
            isInitialized -> if (isAuthenticated) onNavigateToChat() else onNavigateToLogin()
        }
    }

    Box(
        modifier = Modifier.fillMaxSize(),
        contentAlignment = Alignment.Center
    ) {
        if (timedOut) {
            Column(
                horizontalAlignment = Alignment.CenterHorizontally,
                modifier = Modifier.padding(32.dp)
            ) {
                Text(
                    text = "Connection timed out",
                    style = MaterialTheme.typography.bodyLarge,
                    color = TextSecondary,
                    textAlign = TextAlign.Center
                )
                Spacer(modifier = Modifier.height(16.dp))
                TextButton(onClick = onNavigateToLogin) {
                    Text("Continue to Sign In")
                }
            }
        } else {
            CircularProgressIndicator()
        }
    }
}
