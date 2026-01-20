package ai.empirico.app.ui.viewmodel

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import ai.empirico.app.data.model.User
import ai.empirico.app.data.repository.AuthRepository
import ai.empirico.app.data.repository.DeletionStatus
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class AuthUiState(
    val isLoading: Boolean = false,
    val isAuthenticated: Boolean = false,
    val currentUser: User? = null,
    val errorMessage: String? = null,
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
    
    private val authRepository: AuthRepository by lazy { AuthRepository(application.applicationContext) }
    
    private val _uiState = MutableStateFlow(AuthUiState())
    val uiState: StateFlow<AuthUiState> = _uiState.asStateFlow()
    
    init {
        // Initialize repository with saved auth data
        viewModelScope.launch {
            authRepository.initialize()
        }
        
        // Observe user state changes
        viewModelScope.launch {
            try {
                authRepository.currentUser.collect { user ->
                    _uiState.value = _uiState.value.copy(
                        isAuthenticated = user != null,
                        currentUser = user
                    )
                }
            } catch (e: Exception) {
                // Handle collection error gracefully
                _uiState.value = _uiState.value.copy(
                    errorMessage = "Error: ${e.message}"
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
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        errorMessage = e.message ?: "Login failed"
                    )
                }
        }
    }
    
    fun register(firstName: String, lastName: String, email: String, password: String) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, errorMessage = null)
            authRepository.register(firstName, lastName, email, password)
                .onSuccess {
                    _uiState.value = _uiState.value.copy(isLoading = false)
                }
                .onFailure { e ->
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        errorMessage = e.message ?: "Registration failed"
                    )
                }
        }
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
    
    fun googleSignIn(idToken: String) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, errorMessage = null)
            authRepository.googleSignIn(idToken)
                .onSuccess { response ->
                    // The repository updates _currentUser.value synchronously, which triggers
                    // the flow collector in init block to update _uiState automatically
                    // Just set loading to false - the flow collector will handle isAuthenticated and currentUser
                    _uiState.value = _uiState.value.copy(isLoading = false)
                }
                .onFailure { e ->
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        errorMessage = e.message ?: "Google Sign-In failed"
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

