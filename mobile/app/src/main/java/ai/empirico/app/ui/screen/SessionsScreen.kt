package ai.empirico.app.ui.screen

import androidx.compose.animation.*
import androidx.compose.animation.core.*
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import ai.empirico.app.data.model.ChatSession
import ai.empirico.app.ui.theme.*
import ai.empirico.app.ui.viewmodel.ChatViewModel
import java.text.SimpleDateFormat
import java.util.Locale

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SessionsScreen(
    onSessionSelected: (ChatSession) -> Unit,
    onNewSession: () -> Unit,
    onBack: () -> Unit,
    viewModel: ChatViewModel = viewModel()
) {
    val uiState by viewModel.uiState.collectAsState()
    var searchText by remember { mutableStateOf("") }

    // Reload sessions when screen becomes visible to get latest session names
    LaunchedEffect(Unit) {
        // Reload sessions to ensure we have the latest session names and order
        // (backend updates names from first user message and sorts by updated_at)
        viewModel.loadSessions()
    }

    val filteredSessions = remember(uiState.sessions, searchText) {
        if (searchText.isBlank()) uiState.sessions
        else uiState.sessions.filter { session ->
            session.session_name.contains(searchText, ignoreCase = true) ||
                session.patient_summary?.contains(searchText, ignoreCase = true) == true
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        "Session History",
                        fontWeight = FontWeight.Bold,
                        style = MaterialTheme.typography.titleLarge,
                        color = TextPrimary
                    )
                },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(
                            Icons.Default.ArrowBack,
                            contentDescription = "Back",
                            tint = TextPrimary
                        )
                    }
                },
                actions = {
                    IconButton(
                        onClick = onNewSession,
                        colors = IconButtonDefaults.iconButtonColors(
                            contentColor = Primary500
                        )
                    ) {
                        Icon(
                            Icons.Default.Add,
                            contentDescription = "New Session"
                        )
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = SurfaceLight
                )
            )
        }
    ) { paddingValues ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(paddingValues)
                .background(BackgroundLight)
        ) {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(16.dp)
            ) {
                // Search Field
                OutlinedTextField(
                    value = searchText,
                    onValueChange = { searchText = it },
                    modifier = Modifier.fillMaxWidth(),
                    placeholder = { Text("Search sessions...", color = TextTertiary) },
                    leadingIcon = {
                        Icon(
                            imageVector = Icons.Default.Search,
                            contentDescription = "Search",
                            tint = TextTertiary
                        )
                    },
                    trailingIcon = {
                        if (searchText.isNotEmpty()) {
                            IconButton(onClick = { searchText = "" }) {
                                Icon(
                                    imageVector = Icons.Default.Close,
                                    contentDescription = "Clear",
                                    tint = TextTertiary,
                                    modifier = Modifier.size(20.dp)
                                )
                            }
                        }
                    },
                    singleLine = true,
                    shape = RoundedCornerShape(12.dp),
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedBorderColor = Primary500,
                        unfocusedBorderColor = BorderLight,
                        focusedLabelColor = Primary500,
                        focusedContainerColor = SurfaceLight,
                        unfocusedContainerColor = SurfaceLight,
                        focusedTextColor = TextPrimary,
                        unfocusedTextColor = TextPrimary
                    )
                )

                when {
                    uiState.isLoading -> {
                        Box(
                            modifier = Modifier.fillMaxSize(),
                            contentAlignment = Alignment.Center
                        ) {
                            CircularProgressIndicator(
                                color = Primary500,
                                strokeWidth = 3.dp
                            )
                        }
                    }

                    filteredSessions.isEmpty() -> {
                        EmptySessionsState(
                            hasSearch = searchText.isNotEmpty(),
                            onNewSession = onNewSession
                        )
                    }

                    else -> {
                        LazyColumn(
                            modifier = Modifier.fillMaxSize(),
                            verticalArrangement = Arrangement.spacedBy(12.dp)
                        ) {
                            itemsIndexed(filteredSessions) { index, session ->
                                AnimatedVisibility(
                                    visible = true,
                                    enter = fadeIn(animationSpec = tween(300)) + 
                                            slideInVertically(
                                                initialOffsetY = { 20 },
                                                animationSpec = tween(300)
                                            )
                                ) {
                                    SessionCard(
                                        session = session,
                                        isSelected = uiState.currentSession?.id == session.id,
                                        onClick = { onSessionSelected(session) }
                                    )
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun EmptySessionsState(
    hasSearch: Boolean,
    onNewSession: () -> Unit
) {
    Box(
        modifier = Modifier.fillMaxSize(),
        contentAlignment = Alignment.Center
    ) {
        Column(
            modifier = Modifier.padding(32.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Text(
                text = if (hasSearch) "No sessions found" else "No sessions available",
                style = MaterialTheme.typography.headlineSmall,
                fontWeight = FontWeight.Bold,
                color = TextPrimary
            )
            Spacer(modifier = Modifier.height(12.dp))
            Text(
                text = if (hasSearch) 
                    "Try adjusting your search terms." 
                else 
                    "Start a new conversation to capture insights and recommendations.",
                style = MaterialTheme.typography.bodyLarge,
                color = TextSecondary,
                textAlign = TextAlign.Center
            )
            if (!hasSearch) {
                Spacer(modifier = Modifier.height(32.dp))
                Button(
                    onClick = onNewSession,
                    shape = RoundedCornerShape(12.dp),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = Primary500,
                        contentColor = Color.White
                    ),
                    elevation = ButtonDefaults.buttonElevation(
                        defaultElevation = 2.dp,
                        pressedElevation = 0.dp
                    ),
                    modifier = Modifier.height(52.dp)
                ) {
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        Icon(
                            Icons.Default.Add,
                            contentDescription = null,
                            modifier = Modifier.size(20.dp)
                        )
                        Text(
                            "Start New Chat",
                            fontWeight = FontWeight.SemiBold,
                            style = MaterialTheme.typography.titleMedium
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun SessionCard(
    session: ChatSession,
    isSelected: Boolean,
    onClick: () -> Unit
) {
    val dateFormat = remember { SimpleDateFormat("MMM dd, yyyy", Locale.getDefault()) }
    val timeFormat = remember { SimpleDateFormat("hh:mm a", Locale.getDefault()) }
    val createdAt = remember(session.created_at) {
        val createdDate = session.created_at
        if (createdDate.isNullOrBlank()) {
            "Unknown date"
        } else {
            try {
                val date = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss", Locale.getDefault()).parse(createdDate)
                if (date != null) {
                    "${dateFormat.format(date)} • ${timeFormat.format(date)}"
                } else {
                    createdDate
                }
            } catch (_: Exception) {
                createdDate
            }
        }
    }
    
    // Get session title - match web view logic
    // Compute directly from session.session_name so it updates when session data changes
    val sessionTitle = remember(session.id, session.session_name) {
        val name = session.session_name ?: ""
        val genericPrefixes = listOf("Diagnosis Session", "Session", "Streaming Session", "New Session", "New Chat")
        val isGenericName = name.isBlank() ||
            genericPrefixes.any { name.startsWith(it, ignoreCase = false) }
        
        if (!isGenericName) {
            // Session name already set by backend from first user message - show it
            // Backend stores up to 50 chars, we can show it directly or truncate for display
            val cleanName = name.replace(Regex("\\.\\.\\.$"), "") // Remove trailing dots if present
            if (cleanName.length > 50) {
                cleanName.substring(0, 50).trim() + "..."
            } else {
                cleanName
            }
        } else {
            // Generic name - show "New conversation" like web view
            "New conversation"
        }
    }

    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(
            containerColor = if (isSelected) 
                Primary500.copy(alpha = 0.1f)
            else 
                SurfaceLight
        ),
        border = androidx.compose.foundation.BorderStroke(
            if (isSelected) 2.dp else 1.dp,
            if (isSelected) Primary500 else BorderLight
        )
    ) {
        Column(
            modifier = Modifier.padding(20.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            Text(
                text = sessionTitle,
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
                color = if (isSelected) Primary500 else TextPrimary
            )
            Text(
                text = createdAt,
                style = MaterialTheme.typography.bodySmall,
                color = if (isSelected) Primary500.copy(alpha = 0.8f) else TextSecondary,
                fontWeight = FontWeight.Medium
            )
            session.patient_summary?.takeIf { it.isNotBlank() }?.let { summary ->
                Text(
                    text = summary,
                    style = MaterialTheme.typography.bodyMedium,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                    color = TextSecondary,
                    lineHeight = MaterialTheme.typography.bodyMedium.lineHeight
                )
            }
        }
    }
}
