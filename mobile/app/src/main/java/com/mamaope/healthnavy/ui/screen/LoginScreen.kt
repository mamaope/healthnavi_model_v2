package com.mamaope.healthnavy.ui.screen

import android.app.Activity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Visibility
import androidx.compose.material.icons.filled.VisibilityOff
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.google.android.gms.auth.api.signin.GoogleSignIn
import com.google.android.gms.common.api.ApiException
import com.mamaope.healthnavy.ui.theme.AccentCoralDark
import com.mamaope.healthnavy.ui.theme.PrimaryBlue
import com.mamaope.healthnavy.ui.theme.PrimaryTeal
import com.mamaope.healthnavy.ui.viewmodel.AuthViewModel
import com.mamaope.healthnavy.util.GoogleSignInHelper

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun LoginScreen(
    onLoginSuccess: () -> Unit,
    onNavigateToRegister: () -> Unit,
    viewModel: AuthViewModel = viewModel()
) {
    var email by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var passwordVisible by remember { mutableStateOf(false) }
    val uiState by viewModel.uiState.collectAsState()
    val context = LocalContext.current
    
    LaunchedEffect(uiState.isAuthenticated) {
        if (uiState.isAuthenticated) {
            onLoginSuccess()
        }
    }
    
    // Google Sign-In launcher
    val googleSignInLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.StartActivityForResult()
    ) { result ->
        if (result.resultCode == Activity.RESULT_OK) {
            val task = GoogleSignIn.getSignedInAccountFromIntent(result.data)
            try {
                val account = task.getResult(ApiException::class.java)
                account?.idToken?.let { idToken ->
                    // ID token received, proceed with sign-in
                    viewModel.googleSignIn(idToken)
                } ?: run {
                    // ID token is null - this shouldn't happen but handle gracefully
                    viewModel.setError("Google Sign-In failed: No ID token received")
                }
            } catch (e: ApiException) {
                // Handle Google Sign-In API exceptions
                val errorMessage = when (e.statusCode) {
                    7 -> "Network error. Please check your connection."
                    12501 -> "Sign in cancelled"
                    4 -> "Sign in required"
                    10 -> "Developer error - check Google Sign-In configuration"
                    8 -> "Internal error - please try again"
                    else -> "Google Sign-In failed: ${e.statusCode}"
                }
                viewModel.setError(errorMessage)
            } catch (e: Exception) {
                // Handle any other exceptions
                viewModel.setError("Google Sign-In error: ${e.message ?: "Unknown error"}")
            }
        } else {
            // User cancelled or sign-in failed
            if (result.resultCode == Activity.RESULT_CANCELED) {
                // User cancelled - don't show error, just clear any previous errors
                viewModel.clearError()
            } else {
                viewModel.setError("Google Sign-In was cancelled or failed")
            }
        }
    }
    
    fun signInWithGoogle() {
        val signInClient = GoogleSignInHelper.getGoogleSignInClient(context)
        val signInIntent = signInClient.signInIntent
        googleSignInLauncher.launch(signInIntent)
    }
    
    Surface(
        modifier = Modifier.fillMaxSize(),
        color = MaterialTheme.colorScheme.background
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(horizontal = 24.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center
        ) {
            // Logo and Branding
            Spacer(modifier = Modifier.height(32.dp))
            
            Text(
                text = "Health",
                style = MaterialTheme.typography.displayMedium,
                fontWeight = FontWeight.Bold,
                color = AccentCoralDark
            )
            Text(
                text = "Navy",
                style = MaterialTheme.typography.displayMedium,
                fontWeight = FontWeight.Bold,
                color = PrimaryBlue
            )
            
            Spacer(modifier = Modifier.height(8.dp))
            
            Text(
                text = "Evidence Based Medical System",
                style = MaterialTheme.typography.titleMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                textAlign = TextAlign.Center,
                modifier = Modifier.padding(bottom = 48.dp)
            )
            
            // Error Message
            if (uiState.errorMessage != null) {
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(bottom = 16.dp),
                    colors = CardDefaults.cardColors(
                        containerColor = MaterialTheme.colorScheme.errorContainer
                    ),
                    shape = RoundedCornerShape(12.dp)
                ) {
                    Text(
                        text = uiState.errorMessage!!,
                        color = MaterialTheme.colorScheme.onErrorContainer,
                        style = MaterialTheme.typography.bodyMedium,
                        modifier = Modifier.padding(16.dp)
                    )
                }
            }
            
            // Email Field
            OutlinedTextField(
                value = email,
                onValueChange = { email = it },
                label = { Text("Email Address") },
                placeholder = { Text("Enter your email") },
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(bottom = 16.dp),
                singleLine = true,
                shape = RoundedCornerShape(12.dp),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = PrimaryTeal,
                    unfocusedBorderColor = MaterialTheme.colorScheme.outline
                )
            )
            
            // Password Field
            OutlinedTextField(
                value = password,
                onValueChange = { password = it },
                label = { Text("Password") },
                placeholder = { Text("Enter your password") },
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(bottom = 24.dp),
                singleLine = true,
                shape = RoundedCornerShape(12.dp),
                visualTransformation = if (passwordVisible) VisualTransformation.None else PasswordVisualTransformation(),
                trailingIcon = {
                    IconButton(onClick = { passwordVisible = !passwordVisible }) {
                        Icon(
                            imageVector = if (passwordVisible) Icons.Default.Visibility else Icons.Default.VisibilityOff,
                            contentDescription = if (passwordVisible) "Hide password" else "Show password"
                        )
                    }
                },
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = PrimaryTeal,
                    unfocusedBorderColor = MaterialTheme.colorScheme.outline
                )
            )
            
            // Sign In Button
            Button(
                onClick = { viewModel.login(email, password) },
                modifier = Modifier
                    .fillMaxWidth()
                    .height(56.dp),
                enabled = !uiState.isLoading && email.isNotBlank() && password.isNotBlank(),
                shape = RoundedCornerShape(12.dp),
                colors = ButtonDefaults.buttonColors(
                    containerColor = PrimaryTeal
                )
            ) {
                if (uiState.isLoading) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(24.dp),
                        color = MaterialTheme.colorScheme.onPrimary
                    )
                } else {
                    Text(
                        "Sign In",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.SemiBold
                    )
                }
            }
            
            // Divider
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(vertical = 24.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                HorizontalDivider(
                    modifier = Modifier.weight(1f),
                    color = MaterialTheme.colorScheme.outline.copy(alpha = 0.5f)
                )
                Text(
                    text = "OR",
                    modifier = Modifier.padding(horizontal = 16.dp),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
                HorizontalDivider(
                    modifier = Modifier.weight(1f),
                    color = MaterialTheme.colorScheme.outline.copy(alpha = 0.5f)
                )
            }
            
            // Google Sign-In Button
            OutlinedButton(
                onClick = { signInWithGoogle() },
                modifier = Modifier
                    .fillMaxWidth()
                    .height(56.dp),
                enabled = !uiState.isLoading,
                shape = RoundedCornerShape(12.dp),
                colors = ButtonDefaults.outlinedButtonColors(
                    contentColor = MaterialTheme.colorScheme.onSurface
                )
            ) {
                Text(
                    "Continue with Google",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Medium
                )
            }
            
            Spacer(modifier = Modifier.height(24.dp))
            
            // Sign Up Link
            Row(
                horizontalArrangement = Arrangement.Center,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = "Don't have an account? ",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
                TextButton(onClick = onNavigateToRegister) {
                    Text(
                        "Sign Up",
                        style = MaterialTheme.typography.bodyMedium,
                        fontWeight = FontWeight.SemiBold,
                        color = PrimaryTeal
                    )
                }
            }
            
            Spacer(modifier = Modifier.height(32.dp))
        }
    }
}
