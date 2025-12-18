package com.mamaope.healthnavy.ui.viewmodel

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.mamaope.healthnavy.data.model.User
import com.mamaope.healthnavy.data.repository.AuthRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class AuthUiState(
    val isLoading: Boolean = false,
    val isAuthenticated: Boolean = false,
    val currentUser: User? = null,
    val errorMessage: String? = null
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
                    // Get the user from the repository's current state
                    val user = authRepository.currentUserValue
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        isAuthenticated = user != null,
                        currentUser = user
                    )
                }
                .onFailure { e ->
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        errorMessage = e.message ?: "Google Sign-In failed"
                    )
                }
        }
    }
}

