package ai.empirico.app.ui.viewmodel

import android.app.Application
import android.content.Intent
import android.util.Log
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import ai.empirico.app.data.model.User
import ai.empirico.app.data.repository.AuthRepository
import ai.empirico.app.data.repository.DeletionStatus
import com.google.android.gms.auth.api.signin.GoogleSignIn
import com.google.android.gms.common.api.ApiException
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.tasks.await

data class AuthUiState(
    val isLoading: Boolean = false,
    val isAuthenticated: Boolean = false,
    val isInitialized: Boolean = false,
    val currentUser: User? = null,
    val errorMessage: String? = null,
    val registerSuccess: Boolean = false,
    val forgotPasswordSuccess: Boolean = false,
    val resetPasswordSuccess: Boolean = false,
    val profileLoading: Boolean = false,
    val profileError: String? = null,
    val profileSuccess: String? = null,
    val deletionStatus: DeletionStatus? = null,
    val deletionLoading: Boolean = false,
    val deletionMessage: String? = null
)

class AuthViewModel(application: Application) : AndroidViewModel(application) {

    private companion object {
        private const val TAG = "AuthViewModel"
    }
    
    private val authRepository: AuthRepository by lazy { AuthRepository(application.applicationContext) }
    
    private val _uiState = MutableStateFlow(AuthUiState())
    val uiState: StateFlow<AuthUiState> = _uiState.asStateFlow()
    
    init {
        // Restore session: load token first, then set authenticated state from persisted user.
        // This keeps users logged in after app close until they log out.
        viewModelScope.launch {
            try {
                authRepository.initialize()
                val persistedUser = authRepository.getPersistedUser()
                _uiState.value = _uiState.value.copy(
                    isInitialized = true,
                    currentUser = persistedUser,
                    isAuthenticated = (persistedUser != null)
                )
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    isInitialized = true,
                    isAuthenticated = false,
                    errorMessage = null
                )
            }
        }

        // Keep UI in sync when user changes (login, logout, profile update)
        viewModelScope.launch {
            try {
                authRepository.currentUser.collect { user ->
                    _uiState.value = _uiState.value.copy(
                        currentUser = user,
                        isAuthenticated = _uiState.value.isInitialized && (user != null)
                    )
                }
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    isInitialized = true,
                    isAuthenticated = false,
                    errorMessage = null
                )
            }
        }
    }
    
    fun login(email: String, password: String) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, errorMessage = null)
            authRepository.login(email, password)
                .onSuccess {
                    _uiState.value = _uiState.value.copy(isLoading = false)
                }
                .onFailure { e ->
                    val msg = e.message ?: ""
                    val userMessage = when {
                        msg.contains("401", ignoreCase = true) || msg.contains("invalid", ignoreCase = true) ->
                            "Invalid email or password. Please try again."
                        msg.contains("network", ignoreCase = true) || msg.contains("unable to resolve", ignoreCase = true) ->
                            "Network error. Please check your connection and try again."
                        msg.contains("timeout", ignoreCase = true) ->
                            "Connection timed out. Please try again."
                        msg.isNotBlank() -> msg
                        else -> "Unable to sign in. Please try again."
                    }
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        errorMessage = userMessage
                    )
                }
        }
    }
    
    fun register(firstName: String, lastName: String, email: String, password: String) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, errorMessage = null)
            authRepository.register(firstName, lastName, email, password)
                .onSuccess {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        registerSuccess = true
                    )
                }
                .onFailure { e ->
                    val msg = e.message ?: ""
                    val userMessage = when {
                        msg.contains("already", ignoreCase = true) || msg.contains("exists", ignoreCase = true) ->
                            "This email is already registered. Please sign in instead."
                        msg.contains("network", ignoreCase = true) || msg.contains("unable to resolve", ignoreCase = true) ->
                            "Network error. Please check your connection and try again."
                        msg.contains("invalid", ignoreCase = true) ->
                            "Please check your details and try again."
                        msg.isNotBlank() -> msg
                        else -> "Unable to create account. Please try again."
                    }
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        errorMessage = userMessage
                    )
                }
        }
    }

    fun clearRegisterSuccess() {
        _uiState.value = _uiState.value.copy(registerSuccess = false)
    }
    
    fun logout() {
        viewModelScope.launch {
            authRepository.logout()
        }
    }
    
    fun clearError() {
        _uiState.value = _uiState.value.copy(errorMessage = null)
    }
    
    fun setError(message: String) {
        _uiState.value = _uiState.value.copy(errorMessage = message)
    }
    
    fun checkAuth() {
        viewModelScope.launch {
            authRepository.getCurrentUser()
                .onFailure {
                    _uiState.value = _uiState.value.copy(isAuthenticated = false)
                }
        }
    }
    
    /**
     * Handle the result from the Google Sign-In activity. Call this from the activity result
     * callback so that token extraction and backend sign-in run in viewModelScope and are not
     * cancelled if the composable is disposed when returning from the account picker.
     */
    fun handleGoogleSignInResult(resultCode: Int, data: Intent?) {
        viewModelScope.launch {
            Log.d(TAG, "handleGoogleSignInResult(resultCode=$resultCode, hasData=${data != null})")
            if (data == null) {
                Log.w(TAG, "Google Sign-In result missing intent data (resultCode=$resultCode)")
                _uiState.value = _uiState.value.copy(
                    errorMessage = "Google Sign-In was cancelled or failed"
                )
                return@launch
            }
            try {
                val task = GoogleSignIn.getSignedInAccountFromIntent(data)
                val account = task.await()
                val idToken = account?.idToken
                if (!idToken.isNullOrBlank()) {
                    Log.d(TAG, "Google Sign-In received idToken (len=${idToken.length})")
                    googleSignIn(idToken)
                } else {
                    Log.w(TAG, "Google Sign-In returned null/blank idToken")
                    // Common in release builds when the release keystore SHA-1 is not added in Google Cloud Console
                    _uiState.value = _uiState.value.copy(
                        errorMessage = "Google Sign-In failed: No ID token. If this is a release build, add your release keystore SHA-1 in Google Cloud Console (see mobile/RELEASE_GOOGLE_SIGNIN.md)."
                    )
                }
            } catch (e: ApiException) {
                Log.w(TAG, "Google Sign-In ApiException status=${e.statusCode}", e)
                val errorMessage = when (e.statusCode) {
                    7 -> "Network error. Please check your connection."
                    12501 -> "Sign in cancelled"
                    4 -> "Sign in required"
                    10 -> "Google Sign-In not configured for this build. Add your release keystore SHA-1 in Google Cloud Console (see RELEASE_GOOGLE_SIGNIN.md)."
                    8 -> "Internal error - please try again"
                    else -> "Google Sign-In failed: ${e.statusCode}"
                }
                _uiState.value = _uiState.value.copy(errorMessage = errorMessage)
            } catch (e: Exception) {
                Log.e(TAG, "Google Sign-In unexpected exception", e)
                _uiState.value = _uiState.value.copy(
                    errorMessage = "Google Sign-In error: ${e.message ?: "Unknown error"}"
                )
            }
        }
    }

    fun googleSignIn(idToken: String) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, errorMessage = null)
            authRepository.googleSignIn(idToken)
                .onSuccess { user ->
                    // Set auth state immediately so navigation runs on first try without waiting for DataStore flow
                    _uiState.value = _uiState.value.copy(
                        currentUser = user,
                        isAuthenticated = _uiState.value.isInitialized,
                        isLoading = false
                    )
                }
                .onFailure { e ->
                    val msg = e.message ?: ""
                    val userMessage = when {
                        msg.contains("network", ignoreCase = true) || msg.contains("unable to resolve", ignoreCase = true) ->
                            "Network error. Please check your connection and try again."
                        msg.contains("403", ignoreCase = true) || msg.contains("disabled", ignoreCase = true) ->
                            "Google Sign-In is not available for this account."
                        msg.isNotBlank() -> msg
                        else -> "Google Sign-In failed. Please try again."
                    }
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        errorMessage = userMessage
                    )
                }
        }
    }
    
    fun forgotPassword(email: String) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(
                isLoading = true, 
                errorMessage = null,
                forgotPasswordSuccess = false
            )
            authRepository.forgotPassword(email)
                .onSuccess {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        forgotPasswordSuccess = true
                    )
                }
                .onFailure { e ->
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        errorMessage = e.message ?: "Failed to send reset email"
                    )
                }
        }
    }
    
    fun resetPassword(token: String, newPassword: String) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(
                isLoading = true,
                errorMessage = null,
                resetPasswordSuccess = false
            )
            authRepository.resetPassword(token, newPassword)
                .onSuccess {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        resetPasswordSuccess = true
                    )
                }
                .onFailure { e ->
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        errorMessage = e.message ?: "Failed to reset password"
                    )
                }
        }
    }
    
    fun clearForgotPasswordSuccess() {
        _uiState.value = _uiState.value.copy(forgotPasswordSuccess = false)
    }
    
    fun clearResetPasswordSuccess() {
        _uiState.value = _uiState.value.copy(resetPasswordSuccess = false)
    }

    fun updateProfile(fullName: String?, medicalProfessionalType: String?) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(profileLoading = true, profileError = null, profileSuccess = null)
            authRepository.updateProfile(fullName, medicalProfessionalType)
                .onSuccess { user ->
                    _uiState.value = _uiState.value.copy(
                        profileLoading = false,
                        profileSuccess = "Profile updated",
                        currentUser = user
                    )
                }
                .onFailure { e ->
                    _uiState.value = _uiState.value.copy(
                        profileLoading = false,
                        profileError = e.message ?: "Failed to update profile"
                    )
                }
        }
    }

    fun changePassword(currentPassword: String, newPassword: String) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(profileLoading = true, profileError = null, profileSuccess = null)
            authRepository.changePassword(currentPassword, newPassword)
                .onSuccess {
                    _uiState.value = _uiState.value.copy(profileLoading = false, profileSuccess = "Password changed")
                }
                .onFailure { e ->
                    _uiState.value = _uiState.value.copy(
                        profileLoading = false,
                        profileError = e.message ?: "Failed to change password"
                    )
                }
        }
    }

    fun clearProfileMessage() {
        _uiState.value = _uiState.value.copy(profileError = null, profileSuccess = null)
    }

    fun loadDeletionStatus() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(deletionLoading = true, deletionMessage = null)
            authRepository.getDeletionStatus()
                .onSuccess { status ->
                    _uiState.value = _uiState.value.copy(deletionStatus = status, deletionLoading = false)
                }
                .onFailure { e ->
                    _uiState.value = _uiState.value.copy(
                        deletionLoading = false,
                        deletionMessage = e.message ?: "Failed to load status"
                    )
                }
        }
    }

    fun requestDataDeletion() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(deletionLoading = true, deletionMessage = null)
            authRepository.requestDataDeletion()
                .onSuccess { msg ->
                    _uiState.value = _uiState.value.copy(deletionLoading = false, deletionMessage = msg)
                    loadDeletionStatus()
                }
                .onFailure { e ->
                    _uiState.value = _uiState.value.copy(
                        deletionLoading = false,
                        deletionMessage = e.message ?: "Failed to request deletion"
                    )
                }
        }
    }

    fun cancelDataDeletion() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(deletionLoading = true, deletionMessage = null)
            authRepository.cancelDataDeletion()
                .onSuccess { msg ->
                    _uiState.value = _uiState.value.copy(deletionLoading = false, deletionMessage = msg)
                    loadDeletionStatus()
                }
                .onFailure { e ->
                    _uiState.value = _uiState.value.copy(
                        deletionLoading = false,
                        deletionMessage = e.message ?: "Failed to cancel"
                    )
                }
        }
    }

    fun clearDeletionMessage() {
        _uiState.value = _uiState.value.copy(deletionMessage = null)
    }
}

