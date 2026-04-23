package ai.empirico.app.ui.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import ai.empirico.app.data.model.ChatMessage
import ai.empirico.app.data.model.ChatSession
import ai.empirico.app.data.model.MessageAuthor
import ai.empirico.app.data.repository.ChatRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.delay

data class ChatUiState(
    val isLoading: Boolean = false,
    val isSending: Boolean = false,
    val messages: List<ChatMessage> = emptyList(),
    val sessions: List<ChatSession> = emptyList(),
    val currentSession: ChatSession? = null,
    val errorMessage: String? = null,
    val authExpired: Boolean = false, // When true, redirect to login instead of showing error
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
            val currentSessionId = _uiState.value.currentSession?.id
            chatRepository.getSessions()
                .onSuccess { sessions ->
                    // Sessions are already sorted in the repository
                    // The flow collector will update the UI state automatically
                    // But we also explicitly update to ensure immediate refresh
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        sessions = sessions
                    )
                    
                    // Update current session if it exists - this ensures we have the latest session name
                    if (currentSessionId != null) {
                        val updatedSession = sessions.find { it.id == currentSessionId }
                        if (updatedSession != null) {
                            chatRepository.setCurrentSession(updatedSession)
                            _uiState.value = _uiState.value.copy(
                                currentSession = updatedSession
                            )
                        }
                    }
                }
                .onFailure { e ->
                    val message = e.message ?: ""
                    val isAuthError = message.contains("not authenticated", ignoreCase = true) ||
                        message.contains("401", ignoreCase = true) ||
                        message.contains("unauthorized", ignoreCase = true) ||
                        message.contains("session expired", ignoreCase = true) ||
                        message.contains("token", ignoreCase = true)
                    if (isAuthError) {
                        // Redirect to login instead of showing error - user must re-authenticate
                        _uiState.value = _uiState.value.copy(
                            isLoading = false,
                            errorMessage = null,
                            authExpired = true
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
    
    fun createSession(sessionName: String = "Session") {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, errorMessage = null)
            // Clear messages first to show empty state
            chatRepository.clearMessages()
            chatRepository.createSession(sessionName)
                .onSuccess { session ->
                    // Session is already set in repository and added to sessions list
                    // Update UI state with the new session
                    // The repository flow collector will automatically update the sessions list
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        currentSession = session,
                        // Ensure the new session is in the sessions list
                        sessions = _uiState.value.sessions.toMutableList().apply {
                            if (!any { it.id == session.id }) {
                                add(0, session) // Add at the beginning (most recent)
                            }
                        }
                    )
                    // Reload sessions in background to ensure we have the latest from backend
                    // This ensures consistency but doesn't block the UI
                    launch {
                        delay(300) // Small delay to ensure backend has committed
                        loadSessions()
                    }
                }
                .onFailure { e ->
                    val message = e.message ?: ""
                    val isAuthError = message.contains("not authenticated", ignoreCase = true) ||
                        message.contains("401", ignoreCase = true) ||
                        message.contains("unauthorized", ignoreCase = true)
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        errorMessage = if (isAuthError) null else message.ifBlank { "Failed to create session" },
                        authExpired = isAuthError
                    )
                }
        }
    }
    
    fun loadSession(sessionId: Int) {
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
                        val message = e.message ?: ""
                        val isAuthError = message.contains("not authenticated", ignoreCase = true) ||
                            message.contains("401", ignoreCase = true) ||
                            message.contains("unauthorized", ignoreCase = true)
                        _uiState.value = _uiState.value.copy(
                            isLoading = false,
                            errorMessage = if (isAuthError) null else message.ifBlank { "Failed to load messages" },
                            authExpired = isAuthError
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
                                    val msg = e.message ?: ""
                                    val isAuthError = msg.contains("not authenticated", ignoreCase = true) ||
                                        msg.contains("401", ignoreCase = true) ||
                                        msg.contains("unauthorized", ignoreCase = true)
                                    _uiState.value = _uiState.value.copy(
                                        isLoading = false,
                                        errorMessage = if (isAuthError) null else msg.ifBlank { "Failed to load messages" },
                                        authExpired = isAuthError
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
                        val msg = e.message ?: ""
                        val isAuthError = msg.contains("not authenticated", ignoreCase = true) ||
                            msg.contains("401", ignoreCase = true) ||
                            msg.contains("unauthorized", ignoreCase = true)
                        _uiState.value = _uiState.value.copy(
                            isLoading = false,
                            errorMessage = if (isAuthError) null else msg.ifBlank { "Failed to load session" },
                            authExpired = isAuthError
                        )
                    }
            }
        }
    }
    
    fun sendMessage(message: String, useDeepSearch: Boolean? = null) {
        if (message.isBlank()) return

        val deepSearch = useDeepSearch ?: _uiState.value.deepSearchEnabled

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

            // Send to API (use explicit deepSearch so performDeepSearch works reliably)
            chatRepository.sendMessage(message, finalSessionId, deepSearch)
                .onSuccess { response ->
                    val aiMessage = ChatMessage(
                        id = (System.currentTimeMillis() + 1).toString(),
                        author = MessageAuthor.ASSISTANT,
                        content = response.modelResponse ?: "",
                        diagnosisComplete = response.diagnosisComplete ?: false,
                        createdAt = System.currentTimeMillis().toString(),
                        messageId = response.messageId
                    )
                    chatRepository.addMessage(aiMessage)
                    
                    // Handle session - backend may have created/updated session
                    val responseSessionId = response.sessionId
                    val actualSessionId = responseSessionId ?: finalSessionId
                    
                    // Backend updates session name from first user message when saving the first message
                    // The update happens synchronously before response, so reload sessions to get updated name
                    if (actualSessionId != null) {
                        // Reload sessions to get updated session name (backend updates name from first message)
                        loadSessions()
                        
                        // If backend created a new session (responseSessionId is different), update current session
                        if (responseSessionId != null && responseSessionId != finalSessionId) {
                            // Backend created a new session - find and set it
                            launch {
                                delay(400) // Wait for loadSessions to complete
                                val updatedSessions = _uiState.value.sessions
                                val session = updatedSessions.find { it.id == responseSessionId }
                                if (session != null) {
                                    chatRepository.setCurrentSession(session)
                                }
                            }
                        }
                    }
                    
                    _uiState.value = _uiState.value.copy(isSending = false)
                }
                .onFailure { e ->
                    val message = e.message ?: ""
                    val isAuthError = message.contains("not authenticated", ignoreCase = true) ||
                        message.contains("401", ignoreCase = true) ||
                        message.contains("unauthorized", ignoreCase = true)
                    if (isAuthError) {
                        _uiState.value = _uiState.value.copy(
                            isSending = false,
                            errorMessage = null,
                            authExpired = true
                        )
                    } else {
                        val errorMessage = ChatMessage(
                            id = (System.currentTimeMillis() + 1).toString(),
                            author = MessageAuthor.ERROR,
                            content = message.ifBlank { "Failed to send message" },
                            createdAt = System.currentTimeMillis().toString()
                        )
                        chatRepository.addMessage(errorMessage)
                        _uiState.value = _uiState.value.copy(
                            isSending = false,
                            errorMessage = message.ifBlank { "Failed to send message" }
                        )
                    }
                }
        }
    }
    
    fun toggleDeepSearch() {
        _uiState.value = _uiState.value.copy(
            deepSearchEnabled = !_uiState.value.deepSearchEnabled
        )
    }
    
    fun performDeepSearch(aiMessage: ChatMessage) {
        // Find the user's question that prompted this AI response
        val currentIndex = _uiState.value.messages.indexOfFirst { it.id == aiMessage.id }
        if (currentIndex > 0) {
            for (i in currentIndex - 1 downTo 0) {
                val message = _uiState.value.messages[i]
                if (message.author == MessageAuthor.USER) {
                    // Pass useDeepSearch = true so the API gets it even though we don't toggle UI state
                    sendMessage(message.content ?: "", useDeepSearch = true)
                    return
                }
            }
        }
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
                        val msg = e.message ?: ""
                        val isAuthError = msg.contains("not authenticated", ignoreCase = true) ||
                            msg.contains("401", ignoreCase = true) || msg.contains("unauthorized", ignoreCase = true)
                        _uiState.value = _uiState.value.copy(
                            feedback = _uiState.value.feedback + (messageId to currentFeedback!!),
                            errorMessage = if (isAuthError) null else msg.ifBlank { "Failed to remove feedback" },
                            authExpired = isAuthError,
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
                        val msg = e.message ?: ""
                        val isAuthError = msg.contains("not authenticated", ignoreCase = true) ||
                            msg.contains("401", ignoreCase = true) || msg.contains("unauthorized", ignoreCase = true)
                        _uiState.value = _uiState.value.copy(
                            feedback = if (currentFeedback != null) {
                                _uiState.value.feedback + (messageId to currentFeedback)
                            } else {
                                _uiState.value.feedback - messageId
                            },
                            errorMessage = if (isAuthError) null else msg.ifBlank { "Failed to submit feedback" },
                            authExpired = isAuthError,
                            isSubmittingFeedback = false
                        )
                    }
            }
        }
    }
    
    
    fun clearError() {
        _uiState.value = _uiState.value.copy(errorMessage = null)
    }

    fun clearAuthExpired() {
        _uiState.value = _uiState.value.copy(authExpired = false)
    }
    
    fun startNewChat() {
        chatRepository.setCurrentSession(null)
        chatRepository.clearMessages()
    }
}

