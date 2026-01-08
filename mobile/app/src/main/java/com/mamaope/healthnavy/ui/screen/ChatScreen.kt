package com.mamaope.healthnavy.ui.screen

import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.List
import androidx.compose.material.icons.filled.Send
import androidx.compose.material3.*
import com.mamaope.healthnavy.util.MessageFormatter
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.painterResource
import com.mamaope.healthnavy.R
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.mamaope.healthnavy.data.model.ChatMessage
import com.mamaope.healthnavy.data.model.MessageAuthor
import com.mamaope.healthnavy.ui.theme.PrimaryTeal
import com.mamaope.healthnavy.ui.viewmodel.ChatUiState
import com.mamaope.healthnavy.ui.viewmodel.ChatViewModel

@OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)
@Composable
fun ChatScreen(
    onLogout: () -> Unit,
    onNavigateToSessions: () -> Unit,
    chatViewModel: ChatViewModel = viewModel()
) {
    var messageText by remember { mutableStateOf("") }
    val uiState by chatViewModel.uiState.collectAsState()
    val listState = rememberLazyListState()

    LaunchedEffect(uiState.messages.size) {
        if (uiState.messages.isNotEmpty()) {
            listState.animateScrollToItem(uiState.messages.size - 1)
        }
    }

    Scaffold(
        containerColor = MaterialTheme.colorScheme.surface,
        topBar = {
            CenterAlignedTopAppBar(
                title = {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Image(
                            painter = painterResource(id = R.drawable.logo),
                            contentDescription = "HealthNavy Logo",
                            modifier = Modifier
                                .height(40.dp)
                                .widthIn(max = 200.dp)
                        )
                    }
                },
                actions = {
                    TextButton(onClick = onNavigateToSessions) {
                        Icon(Icons.Default.List, contentDescription = null)
                        Spacer(modifier = Modifier.width(4.dp))
                        Text("Sessions")
                    }
                    TextButton(onClick = onLogout) {
                        Text("Logout")
                    }
                },
                colors = TopAppBarDefaults.centerAlignedTopAppBarColors(
                    containerColor = MaterialTheme.colorScheme.surface
                )
            )
        },
        bottomBar = {
            InputArea(
                messageText = messageText,
                onMessageChange = { messageText = it },
                isSending = uiState.isSending,
                isDeepSearch = uiState.deepSearchEnabled,
                onToggleDeepSearch = { chatViewModel.toggleDeepSearch() },
                onSend = {
                    if (messageText.isNotBlank()) {
                        chatViewModel.sendMessage(messageText.trim())
                        messageText = ""
                    }
                },
                errorMessage = uiState.errorMessage
            )
        }
    ) { paddingValues ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(paddingValues)
                .background(
                    brush = Brush.verticalGradient(
                        colors = listOf(
                            MaterialTheme.colorScheme.surface,
                            MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.3f)
                        )
                    )
                )
                .padding(horizontal = 16.dp, vertical = 12.dp)
        ) {
            Box(modifier = Modifier.weight(1f)) {
                ConversationArea(
                    uiState = uiState,
                    listState = listState,
                    chatViewModel = chatViewModel
                )
            }
        }
    }
}

@Composable
private fun ConversationArea(
    uiState: com.mamaope.healthnavy.ui.viewmodel.ChatUiState,
    listState: androidx.compose.foundation.lazy.LazyListState,
    chatViewModel: ChatViewModel
) {
    Surface(
        modifier = Modifier.fillMaxSize(),
        color = MaterialTheme.colorScheme.surface,
        tonalElevation = 2.dp,
        shape = RoundedCornerShape(24.dp)
    ) {
        if (uiState.messages.isEmpty() && !uiState.isLoading) {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(24.dp),
                verticalArrangement = Arrangement.Center,
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                Text(
                    "Start a Conversation",
                    style = MaterialTheme.typography.titleLarge,
                    fontWeight = FontWeight.SemiBold
                )
                Text(
                    text = "Ask questions or share information to get helpful responses.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    textAlign = androidx.compose.ui.text.style.TextAlign.Center,
                    modifier = Modifier.padding(top = 12.dp)
                )
                Spacer(modifier = Modifier.height(24.dp))
                SamplePromptChips(onPromptSelected = {
                    chatViewModel.sendMessage(it)
                })
            }
        } else {
            LazyColumn(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(vertical = 16.dp),
                contentPadding = PaddingValues(horizontal = 16.dp, vertical = 8.dp),
                state = listState,
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                items(uiState.messages) { message ->
                    MessageBubble(message = message, viewModel = chatViewModel)
                }
                if (uiState.isSending) {
                    item {
                        Box(
                            modifier = Modifier.fillMaxWidth(),
                            contentAlignment = Alignment.Center
                        ) {
                            CircularProgressIndicator(
                                modifier = Modifier.size(32.dp)
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun SamplePromptChips(onPromptSelected: (String) -> Unit) {
    val prompts = listOf(
        "Patient with fever, tachycardia, and chest pain",
        "Interpret lab panel showing elevated AST/ALT",
        "Differential for acute onset shortness of breath",
        "Management steps for suspected sepsis"
    )

    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        prompts.forEach { prompt ->
            OutlinedButton(
                onClick = { onPromptSelected(prompt) },
                shape = RoundedCornerShape(16.dp),
                border = androidx.compose.foundation.BorderStroke(
                    1.dp,
                    MaterialTheme.colorScheme.outline.copy(alpha = 0.3f)
                ),
                colors = androidx.compose.material3.ButtonDefaults.outlinedButtonColors(
                    containerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.6f),
                    contentColor = MaterialTheme.colorScheme.onSurface
                ),
                modifier = Modifier.fillMaxWidth()
            ) {
                Text(
                    prompt,
                    style = MaterialTheme.typography.bodyMedium,
                    modifier = Modifier.padding(vertical = 4.dp)
                )
            }
        }
    }
}

@Composable
private fun InputArea(
    messageText: String,
    onMessageChange: (String) -> Unit,
    isSending: Boolean,
    isDeepSearch: Boolean,
    onToggleDeepSearch: () -> Unit,
    onSend: () -> Unit,
    errorMessage: String?
) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .background(MaterialTheme.colorScheme.surface)
            .windowInsetsPadding(WindowInsets.navigationBars)
            .padding(horizontal = 16.dp, vertical = 12.dp)
    ) {
        if (!errorMessage.isNullOrEmpty()) {
            Text(
                text = errorMessage,
                color = MaterialTheme.colorScheme.error,
                style = MaterialTheme.typography.bodySmall,
                modifier = Modifier.padding(bottom = 8.dp)
            )
        }
        
        Card(
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(24.dp),
            elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
            colors = CardDefaults.cardColors(
                containerColor = MaterialTheme.colorScheme.surface
            )
        ) {
            Column(modifier = Modifier.padding(16.dp)) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    // Deep Search Toggle Button
                    IconButton(
                        onClick = onToggleDeepSearch,
                        modifier = Modifier.size(40.dp)
                    ) {
                        Icon(
                            imageVector = Icons.Default.AutoAwesome,
                            contentDescription = if (isDeepSearch) "Deep search enabled" else "Deep search disabled",
                            tint = if (isDeepSearch) PrimaryTeal else MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.size(22.dp)
                        )
                    }
                    
                    OutlinedTextField(
                        value = messageText,
                        onValueChange = onMessageChange,
                        modifier = Modifier.weight(1f),
                        placeholder = { Text("Describe symptoms, history, or diagnostic questions...") },
                        maxLines = 6,
                        shape = RoundedCornerShape(16.dp),
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedBorderColor = PrimaryTeal,
                            unfocusedBorderColor = MaterialTheme.colorScheme.outline.copy(alpha = 0.5f),
                            focusedLabelColor = PrimaryTeal
                        ),
                        trailingIcon = {
                    FilledIconButton(
                        onClick = onSend,
                        enabled = messageText.isNotBlank() && !isSending,
                        colors = androidx.compose.material3.IconButtonDefaults.filledIconButtonColors(
                                    containerColor = if (messageText.isNotBlank()) PrimaryTeal else MaterialTheme.colorScheme.surfaceVariant
                        ),
                                shape = CircleShape,
                                modifier = Modifier.size(40.dp)
                    ) {
                        if (isSending) {
                            CircularProgressIndicator(
                                        modifier = Modifier.size(18.dp),
                                strokeWidth = 2.dp,
                                color = Color.White
                            )
                        } else {
                            Icon(
                                imageVector = Icons.Default.Send,
                                contentDescription = "Send",
                                        tint = Color.White,
                                        modifier = Modifier.size(18.dp)
                            )
                        }
                    }
                        }
                    )
                }
            }
        }
    }
}

@Composable
private fun AssistiveBadge(label: String, color: Color, textColor: Color) {
    Surface(
        color = color,
        contentColor = textColor,
        shape = RoundedCornerShape(50),
        tonalElevation = 3.dp
    ) {
        Text(
            text = label,
            style = MaterialTheme.typography.labelMedium,
            modifier = Modifier.padding(horizontal = 12.dp, vertical = 6.dp)
        )
    }
}

@Composable
fun MessageBubble(
    message: ChatMessage,
    viewModel: ChatViewModel
) {
    val isUser = message.author == MessageAuthor.USER
    val isError = message.author == MessageAuthor.ERROR

    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = if (isUser) Arrangement.End else Arrangement.Start
    ) {
        Card(
            modifier = Modifier
                .widthIn(max = 280.dp)
                .shadow(2.dp, RoundedCornerShape(20.dp)),
            shape = RoundedCornerShape(
                topStart = 20.dp,
                topEnd = 20.dp,
                bottomEnd = if (isUser) 4.dp else 20.dp,
                bottomStart = if (isUser) 20.dp else 4.dp
            ),
            colors = CardDefaults.cardColors(
                containerColor = when {
                    isError -> MaterialTheme.colorScheme.errorContainer
                    isUser -> PrimaryTeal
                    else -> MaterialTheme.colorScheme.surface
                }
            ),
            elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
        ) {
            Column(modifier = Modifier.padding(16.dp)) {
                if (message.author == MessageAuthor.ASSISTANT && !isError) {
                    // Format AI responses with markdown
                    Text(
                        text = MessageFormatter.formatMessage(message.content),
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurface,
                        lineHeight = MaterialTheme.typography.bodyMedium.lineHeight
                    )
                } else {
                    // Regular text for user messages and errors
                    Text(
                        text = message.content,
                        style = MaterialTheme.typography.bodyMedium,
                        color = when {
                            isError -> MaterialTheme.colorScheme.onErrorContainer
                            isUser -> Color.White
                            else -> MaterialTheme.colorScheme.onSurface
                        },
                        lineHeight = MaterialTheme.typography.bodyMedium.lineHeight
                    )
                }
                if (message.author == MessageAuthor.ASSISTANT && message.messageId != null) {
                    Spacer(modifier = Modifier.height(12.dp))
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        FeedbackChip(label = "Helpful") {
                            viewModel.submitFeedback(message.messageId, "helpful")
                        }
                        FeedbackChip(label = "Needs review") {
                            viewModel.submitFeedback(message.messageId, "not_helpful")
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun FeedbackChip(label: String, onClick: () -> Unit) {
    OutlinedButton(
        onClick = onClick,
        shape = RoundedCornerShape(20.dp),
        border = androidx.compose.foundation.BorderStroke(
            1.dp,
            MaterialTheme.colorScheme.outline.copy(alpha = 0.5f)
        ),
        colors = androidx.compose.material3.ButtonDefaults.outlinedButtonColors(
            contentColor = MaterialTheme.colorScheme.onSurfaceVariant,
            containerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.5f)
        )
    ) {
        Text(
            label,
            style = MaterialTheme.typography.labelMedium,
            fontWeight = FontWeight.Medium
        )
    }
}

