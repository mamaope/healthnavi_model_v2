package com.mamaope.healthnavy.ui.screen

import androidx.compose.animation.*
import androidx.compose.animation.core.*
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.List
import androidx.compose.material.icons.filled.Send
import androidx.compose.material.icons.filled.ThumbUp
import androidx.compose.material.icons.filled.ThumbDown
import androidx.compose.material.icons.filled.Share
import androidx.compose.material3.*
import com.mamaope.healthnavy.util.MessageFormatter
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.painterResource
import com.mamaope.healthnavy.R
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.platform.LocalContext
import androidx.lifecycle.viewmodel.compose.viewModel
import android.content.Intent
import com.mamaope.healthnavy.data.model.ChatMessage
import com.mamaope.healthnavy.data.model.MessageAuthor
import com.mamaope.healthnavy.ui.theme.*
import com.mamaope.healthnavy.ui.viewmodel.ChatUiState
import com.mamaope.healthnavy.ui.viewmodel.ChatViewModel

@OptIn(ExperimentalMaterial3Api::class)
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
        containerColor = BackgroundLight,
        topBar = {
            TopAppBar(
                title = {
                    Image(
                        painter = painterResource(id = R.drawable.logo),
                        contentDescription = "Empirico Logo",
                        modifier = Modifier.height(32.dp)
                    )
                },
                actions = {
                    IconButton(onClick = onNavigateToSessions) {
                        Icon(
                            Icons.Default.List,
                            contentDescription = "Sessions",
                            tint = Primary500
                        )
                    }
                    TextButton(onClick = onLogout) {
                        Text(
                            "Logout",
                            color = TextSecondary,
                            style = MaterialTheme.typography.bodyMedium
                        )
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = SurfaceLight
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
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(paddingValues)
                .background(BackgroundLight)
    ) {
        if (uiState.messages.isEmpty() && !uiState.isLoading) {
                EmptyChatState(onPromptSelected = {
                    chatViewModel.sendMessage(it)
                })
        } else {
            LazyColumn(
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = PaddingValues(horizontal = 16.dp, vertical = 16.dp),
                state = listState,
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                    itemsIndexed(uiState.messages) { index, message ->
                        AnimatedVisibility(
                            visible = true,
                            enter = fadeIn(animationSpec = tween(300)) + 
                                    slideInVertically(
                                        initialOffsetY = { 20 },
                                        animationSpec = tween(300)
                                    )
                        ) {
                            MessageBubble(
                                message = message,
                                viewModel = chatViewModel
                            )
                        }
                }
                if (uiState.isSending) {
                    item {
                            ThinkingIndicator()
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun EmptyChatState(onPromptSelected: (String) -> Unit) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(32.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Text(
            "Start a Conversation",
            style = MaterialTheme.typography.headlineMedium,
            fontWeight = FontWeight.Bold,
            color = TextPrimary
        )
        Spacer(modifier = Modifier.height(12.dp))
        Text(
            text = "Ask questions or share information to get helpful responses.",
            style = MaterialTheme.typography.bodyLarge,
            color = TextSecondary,
            textAlign = androidx.compose.ui.text.style.TextAlign.Center
        )
        Spacer(modifier = Modifier.height(32.dp))
        SamplePromptChips(onPromptSelected = onPromptSelected)
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
            Card(
                onClick = { onPromptSelected(prompt) },
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(12.dp),
                colors = CardDefaults.cardColors(
                    containerColor = SurfaceLight
                ),
                border = androidx.compose.foundation.BorderStroke(
                    1.dp,
                    BorderLight
                )
            ) {
                Text(
                    prompt,
                    style = MaterialTheme.typography.bodyMedium,
                    color = TextPrimary,
                    modifier = Modifier.padding(16.dp)
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
            .background(SurfaceLight)
            .windowInsetsPadding(WindowInsets.navigationBars)
            .padding(16.dp)
    ) {
        AnimatedVisibility(
            visible = !errorMessage.isNullOrEmpty(),
            enter = fadeIn() + slideInVertically(),
            exit = fadeOut() + slideOutVertically()
        ) {
            errorMessage?.let {
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(bottom = 12.dp),
                    colors = CardDefaults.cardColors(
                        containerColor = Error500.copy(alpha = 0.1f)
                    ),
                    shape = RoundedCornerShape(12.dp),
                    border = androidx.compose.foundation.BorderStroke(
                        1.dp,
                        Error500.copy(alpha = 0.3f)
                    )
                ) {
            Text(
                        text = it,
                        color = Error600,
                style = MaterialTheme.typography.bodySmall,
                        modifier = Modifier.padding(12.dp)
            )
                }
            }
        }
        
        Card(
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(24.dp),
            colors = CardDefaults.cardColors(
                containerColor = SurfaceLight
            ),
            border = androidx.compose.foundation.BorderStroke(
                1.dp,
                if (isDeepSearch) Primary500 else BorderLight
                    )
        ) {
            Row(
                modifier = Modifier.padding(horizontal = 4.dp, vertical = 4.dp),
                    verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                Surface(
                    onClick = onToggleDeepSearch,
                    modifier = Modifier.size(44.dp),
                    shape = CircleShape,
                    color = if (isDeepSearch) Primary500.copy(alpha = 0.1f) else Gray100,
                    border = androidx.compose.foundation.BorderStroke(
                        1.dp,
                        if (isDeepSearch) Primary500 else BorderLight
                    )
                ) {
                    Box(contentAlignment = Alignment.Center) {
                        Icon(
                            imageVector = Icons.Default.AutoAwesome,
                            contentDescription = if (isDeepSearch) "Deep search enabled" else "Deep search disabled",
                            tint = if (isDeepSearch) Primary500 else TextTertiary,
                            modifier = Modifier.size(22.dp)
                        )
                    }
                }
                
                OutlinedTextField(
                    value = messageText,
                    onValueChange = onMessageChange,
                    modifier = Modifier.weight(1f),
                    placeholder = { Text("Type your message...", color = TextTertiary) },
                    maxLines = 5,
                    shape = RoundedCornerShape(20.dp),
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedBorderColor = Color.Transparent,
                        unfocusedBorderColor = Color.Transparent,
                        focusedContainerColor = Color.Transparent,
                        unfocusedContainerColor = Color.Transparent,
                        focusedTextColor = TextPrimary,
                        unfocusedTextColor = TextPrimary
                    ),
                    trailingIcon = {
                    FilledIconButton(
                        onClick = onSend,
                        enabled = messageText.isNotBlank() && !isSending,
                            colors = IconButtonDefaults.filledIconButtonColors(
                                containerColor = if (messageText.isNotBlank()) Primary500 else Gray300,
                                disabledContainerColor = Gray300
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

@Composable
fun MessageBubble(
    message: ChatMessage,
    viewModel: ChatViewModel
) {
    val context = LocalContext.current
    val uiState by viewModel.uiState.collectAsState()
    val isUser = message.author == MessageAuthor.USER
    val isError = message.author == MessageAuthor.ERROR

    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = if (isUser) Arrangement.End else Arrangement.Center
    ) {
        Card(
            modifier = Modifier
                .then(
                    if (isUser) {
                        Modifier.widthIn(max = 280.dp)
                    } else {
                        Modifier.fillMaxWidth(0.9f)
                    }
                ),
            shape = RoundedCornerShape(
                topStart = 20.dp,
                topEnd = 20.dp,
                bottomEnd = if (isUser) 4.dp else 20.dp,
                bottomStart = if (isUser) 20.dp else 4.dp
            ),
            colors = CardDefaults.cardColors(
                containerColor = when {
                    isError -> Error500.copy(alpha = 0.1f)
                    isUser -> Primary500
                    else -> Gray100
                }
            ),
            border = when {
                isError -> androidx.compose.foundation.BorderStroke(1.dp, Error500.copy(alpha = 0.3f))
                isUser -> null
                else -> androidx.compose.foundation.BorderStroke(1.dp, BorderLight)
            }
        ) {
            Column(modifier = Modifier.padding(16.dp)) {
                val content = message.content ?: ""
                if (message.author == MessageAuthor.ASSISTANT && !isError) {
                    Text(
                        text = MessageFormatter.formatMessage(content),
                        style = MaterialTheme.typography.bodyMedium,
                        color = TextPrimary,
                        lineHeight = MaterialTheme.typography.bodyMedium.lineHeight
                    )
                } else {
                    Text(
                        text = content,
                        style = MaterialTheme.typography.bodyMedium,
                        color = when {
                            isError -> Error600
                            isUser -> Color.White
                            else -> TextPrimary
                        },
                        lineHeight = MaterialTheme.typography.bodyMedium.lineHeight
                    )
                }
                if (message.author == MessageAuthor.ASSISTANT && message.messageId != null) {
                    Spacer(modifier = Modifier.height(12.dp))
                    val feedbackState = uiState.feedback[message.messageId]
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        FeedbackChip(
                            label = "Helpful",
                            icon = Icons.Default.ThumbUp,
                            isActive = feedbackState == "helpful",
                            onClick = {
                                viewModel.submitFeedback(message.messageId!!, "helpful")
                        }
                        )
                        FeedbackChip(
                            label = "Not helpful",
                            icon = Icons.Default.ThumbDown,
                            isActive = feedbackState == "not_helpful",
                            onClick = {
                                viewModel.submitFeedback(message.messageId!!, "not_helpful")
                        }
                        )
                        FeedbackChip(
                            label = "Share",
                            icon = Icons.Default.Share,
                            isActive = false,
                            onClick = {
                                val shareIntent = Intent(Intent.ACTION_SEND).apply {
                                    type = "text/plain"
                                    putExtra(Intent.EXTRA_TEXT, message.content ?: "")
                                    putExtra(Intent.EXTRA_SUBJECT, "Empirico AI Response")
                                }
                                context.startActivity(Intent.createChooser(shareIntent, "Share via"))
                            }
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun FeedbackChip(
    label: String,
    icon: androidx.compose.ui.graphics.vector.ImageVector? = null,
    isActive: Boolean = false,
    onClick: () -> Unit
) {
    Surface(
        onClick = onClick,
        shape = RoundedCornerShape(16.dp),
        color = if (isActive) Primary500 else SurfaceLight,
        border = androidx.compose.foundation.BorderStroke(
            width = if (isActive) 2.dp else 1.dp,
            color = if (isActive) Primary500 else BorderLight
        ),
        modifier = Modifier.size(40.dp),
        shadowElevation = if (isActive) 4.dp else 0.dp
    ) {
        Box(
            modifier = Modifier.fillMaxSize(),
            contentAlignment = Alignment.Center
        ) {
            if (icon != null) {
                Icon(
                    imageVector = icon,
                    contentDescription = label,
                    modifier = Modifier.size(20.dp),
                    tint = if (isActive) Color.White else TextSecondary
                )
            }
        }
    }
}

@Composable
private fun ThinkingIndicator() {
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 8.dp),
        contentAlignment = Alignment.CenterStart
    ) {
        Card(
            modifier = Modifier.widthIn(max = 200.dp),
            shape = RoundedCornerShape(20.dp),
            colors = CardDefaults.cardColors(
                containerColor = Gray100
            ),
            border = androidx.compose.foundation.BorderStroke(1.dp, BorderLight)
        ) {
            Row(
                modifier = Modifier.padding(16.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(12.dp)
    ) {
                CircularProgressIndicator(
                    modifier = Modifier.size(20.dp),
                    strokeWidth = 2.dp,
                    color = Primary500
                )
                Text(
                    "Thinking...",
                    style = MaterialTheme.typography.bodySmall,
                    color = TextSecondary
                )
    }
}
    }
}
