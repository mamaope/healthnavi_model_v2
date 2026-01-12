package com.mamaope.healthnavy.ui.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.mamaope.healthnavy.data.model.ChatMessage
import com.mamaope.healthnavy.data.model.ChatSession
import com.mamaope.healthnavy.data.model.DiagnosisResponse
import com.mamaope.healthnavy.data.model.MessageAuthor
import com.mamaope.healthnavy.data.repository.ChatRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class ChatUiState(
    val isLoading: Boolean = false,
    val isSending: Boolean = false,
    val messages: List<ChatMessage> = emptyList(),
    val sessions: List<ChatSession> = emptyList(),
    val currentSession: ChatSession? = null,
    val errorMessage: String? = null,
    val deepSearchEnabled: Boolean = false,
    val feedback: Map<Int, String> = emptyMap(), // messageId -> feedbackType ("helpful" or "not_helpful")
    val feedbackDialogOpen: Boolean = false,
    val selectedFeedbackMessageId: Int? = null,
    val selectedFeedbackType: String? = null, // "helpful" or "not_helpful"
    val isSubmittingFeedback: Boolean = false
)

class ChatViewModel : ViewModel() {
    
    private val chatRepository: ChatRepository by lazy { ChatRepository() }
    
    private val _uiState = MutableStateFlow(ChatUiState())
    val uiState: StateFlow<ChatUiState> = _uiState.asStateFlow()
    
    init {
        viewModelScope.launch {
            chatRepository.messages.collect { messages ->
                _uiState.value = _uiState.value.copy(messages = messages)
            }
        }
        
        viewModelScope.launch {
            chatRepository.sessions.collect { sessions ->
                _uiState.value = _uiState.value.copy(sessions = sessions)
            }
        }
        
        viewModelScope.launch {
            chatRepository.currentSession.collect { session ->
                _uiState.value = _uiState.value.copy(currentSession = session)
            }
        }
        
        loadSessions()
    }
    
    fun loadSessions() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true)
            chatRepository.getSessions()
                .onSuccess {
                    _uiState.value = _uiState.value.copy(isLoading = false)
                }
                .onFailure { e ->
                    // When the user is not authenticated yet, the backend may return
                    // a "Not authenticated" error. This commonly happens on app start
                    // before login. We don't want to surface this to the user as an
                    // error message in the chat UI, so we silently ignore it.
                    val message = e.message ?: ""
                    if (message.contains("not authenticated", ignoreCase = true)) {
                        _uiState.value = _uiState.value.copy(
                            isLoading = false,
                            errorMessage = null
                        )
                    } else {
                        _uiState.value = _uiState.value.copy(
                            isLoading = false,
                            errorMessage = message.ifBlank { "Failed to load sessions" }
                        )
                    }
                }
        }
    }
    
    fun createSession(sessionName: String = "New Chat") {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, errorMessage = null)
            // Clear messages first to show empty state
            chatRepository.clearMessages()
            chatRepository.createSession(sessionName)
                .onSuccess { session ->
                    // Session is already set in repository
                    // For a new session, messages will be empty, so we don't need to load them
                    // Just update UI state and reload sessions list
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        currentSession = session
                    )
                    // Reload sessions to update the list
                    loadSessions()
                }
                .onFailure { e ->
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        errorMessage = e.message ?: "Failed to create session"
                    )
                }
        }
    }
    
    fun loadSession(sessionId: String) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, errorMessage = null)
            
            // Clear current messages first
            chatRepository.clearMessages()
            
            val session = _uiState.value.sessions.find { it.id == sessionId }
            if (session != null) {
                chatRepository.setCurrentSession(session)
                chatRepository.getSessionMessages(sessionId)
                    .onSuccess {
                        _uiState.value = _uiState.value.copy(isLoading = false)
                    }
                    .onFailure { e ->
                        _uiState.value = _uiState.value.copy(
                            isLoading = false,
                            errorMessage = e.message ?: "Failed to load messages"
                        )
                    }
            } else {
                // Session not found in current list, try reloading sessions first
                chatRepository.getSessions()
                    .onSuccess {
                        val updatedSession = _uiState.value.sessions.find { it.id == sessionId }
                        if (updatedSession != null) {
                            chatRepository.setCurrentSession(updatedSession)
                            chatRepository.getSessionMessages(sessionId)
                                .onSuccess {
                                    _uiState.value = _uiState.value.copy(isLoading = false)
                                }
                                .onFailure { e ->
                                    _uiState.value = _uiState.value.copy(
                                        isLoading = false,
                                        errorMessage = e.message ?: "Failed to load messages"
                                    )
                                }
                        } else {
                            _uiState.value = _uiState.value.copy(
                                isLoading = false,
                                errorMessage = "Session not found"
                            )
                        }
                    }
                    .onFailure { e ->
                        _uiState.value = _uiState.value.copy(
                            isLoading = false,
                            errorMessage = e.message ?: "Failed to load session"
                        )
                    }
            }
        }
    }
    
    fun sendMessage(message: String) {
        if (message.isBlank()) return
        
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isSending = true, errorMessage = null)
            
            // Add user message immediately
            val userMessage = ChatMessage(
                id = System.currentTimeMillis().toString(),
                author = MessageAuthor.USER,
                content = message,
                createdAt = System.currentTimeMillis().toString()
            )
            chatRepository.addMessage(userMessage)
            
            // Get or create session
            val sessionId = _uiState.value.currentSession?.id
            val finalSessionId = if (sessionId == null) {
                chatRepository.createSession().getOrNull()?.id
            } else {
                sessionId
            }
            
            // Send to API
            chatRepository.sendMessage(message, finalSessionId, _uiState.value.deepSearchEnabled)
                .onSuccess { response ->
                    val aiMessage = ChatMessage(
                        id = (System.currentTimeMillis() + 1).toString(),
                        author = MessageAuthor.ASSISTANT,
                        content = response.data.model_response ?: "",
                        diagnosisComplete = response.data.diagnosis_complete ?: false,
                        createdAt = System.currentTimeMillis().toString(),
                        messageId = response.data.message_id
                    )
                    chatRepository.addMessage(aiMessage)
                    
                    // Update session if created
                    if (finalSessionId != null && _uiState.value.currentSession == null) {
                        loadSessions()
                    }
                    
                    _uiState.value = _uiState.value.copy(isSending = false)
                }
                .onFailure { e ->
                    val errorMessage = ChatMessage(
                        id = (System.currentTimeMillis() + 1).toString(),
                        author = MessageAuthor.ERROR,
                        content = e.message ?: "Failed to send message",
                        createdAt = System.currentTimeMillis().toString()
                    )
                    chatRepository.addMessage(errorMessage)
                    _uiState.value = _uiState.value.copy(
                        isSending = false,
                        errorMessage = e.message ?: "Failed to send message"
                    )
                }
        }
    }
    
    fun toggleDeepSearch() {
        _uiState.value = _uiState.value.copy(
            deepSearchEnabled = !_uiState.value.deepSearchEnabled
        )
    }
    
    fun openFeedbackDialog(messageId: Int, feedbackType: String) {
        val currentFeedback = _uiState.value.feedback[messageId]
        val isRemoving = currentFeedback == feedbackType
        
        if (isRemoving) {
            // Remove feedback directly if clicking the same button
            submitFeedback(messageId, feedbackType, null, null, true)
        } else {
            // Open dialog for new feedback
            _uiState.value = _uiState.value.copy(
                feedbackDialogOpen = true,
                selectedFeedbackMessageId = messageId,
                selectedFeedbackType = feedbackType
            )
        }
    }
    
    fun closeFeedbackDialog() {
        _uiState.value = _uiState.value.copy(
            feedbackDialogOpen = false,
            selectedFeedbackMessageId = null,
            selectedFeedbackType = null
        )
    }
    
    fun submitFeedback(
        messageId: Int,
        feedbackType: String,
        feedbackText: String? = null,
        rating: Int? = null,
        isRemoving: Boolean = false
    ) {
        viewModelScope.launch {
            val currentFeedback = _uiState.value.feedback[messageId]
            
            // Update UI state immediately for better UX
            val newFeedbackMap = if (isRemoving) {
                _uiState.value.feedback - messageId
            } else {
                // If switching from one feedback to another, remove the old one first
                val feedbackWithoutThis = if (currentFeedback != null && currentFeedback != feedbackType) {
                    _uiState.value.feedback - messageId
                } else {
                    _uiState.value.feedback
                }
                feedbackWithoutThis + (messageId to feedbackType)
            }
            
            _uiState.value = _uiState.value.copy(
                feedback = newFeedbackMap,
                isSubmittingFeedback = true
            )
            
            if (isRemoving) {
                // Remove feedback
                chatRepository.removeFeedback(messageId)
                    .onSuccess {
                        _uiState.value = _uiState.value.copy(isSubmittingFeedback = false)
                    }
                    .onFailure { e ->
                        // Revert on failure
                        _uiState.value = _uiState.value.copy(
                            feedback = _uiState.value.feedback + (messageId to currentFeedback!!),
                            errorMessage = e.message ?: "Failed to remove feedback",
                            isSubmittingFeedback = false
                        )
                    }
            } else {
                // Submit feedback with rating and text
                chatRepository.submitFeedback(messageId, feedbackType, feedbackText, rating)
                    .onSuccess {
                        _uiState.value = _uiState.value.copy(
                            isSubmittingFeedback = false,
                            feedbackDialogOpen = false,
                            selectedFeedbackMessageId = null,
                            selectedFeedbackType = null
                        )
                    }
                    .onFailure { e ->
                        // Revert on failure
                        _uiState.value = _uiState.value.copy(
                            feedback = if (currentFeedback != null) {
                                _uiState.value.feedback + (messageId to currentFeedback)
                            } else {
                                _uiState.value.feedback - messageId
                            },
                            errorMessage = e.message ?: "Failed to submit feedback",
                            isSubmittingFeedback = false
                        )
                    }
            }
        }
    }
    
    
    fun clearError() {
        _uiState.value = _uiState.value.copy(errorMessage = null)
    }
    
    fun startNewChat() {
        chatRepository.setCurrentSession(null)
        chatRepository.clearMessages()
    }
}

