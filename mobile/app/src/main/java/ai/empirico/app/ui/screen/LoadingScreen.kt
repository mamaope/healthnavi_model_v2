package ai.empirico.app.ui.screen

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import ai.empirico.app.ui.viewmodel.AuthViewModel

/**
 * Shown on app start until auth is initialized (token restored).
 * Then navigates to Chat (if logged in) or Login.
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

    LaunchedEffect(isInitialized) {
        if (isInitialized) {
            if (isAuthenticated) onNavigateToChat() else onNavigateToLogin()
        }
    }

    Box(
        modifier = Modifier.fillMaxSize(),
        contentAlignment = Alignment.Center
    ) {
        CircularProgressIndicator()
    }
}
