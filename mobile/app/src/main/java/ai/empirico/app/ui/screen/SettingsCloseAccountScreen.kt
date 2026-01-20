package ai.empirico.app.ui.screen

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import ai.empirico.app.ui.theme.*
import ai.empirico.app.ui.viewmodel.AuthViewModel

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsCloseAccountScreen(
    onBack: () -> Unit,
    viewModel: AuthViewModel = viewModel()
) {
    val uiState by viewModel.uiState.collectAsState()
    var showConfirm by remember { mutableStateOf(false) }

    LaunchedEffect(Unit) { viewModel.loadDeletionStatus() }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Close Account", fontWeight = FontWeight.SemiBold) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back", tint = TextPrimary)
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = SurfaceLight)
            )
        },
        containerColor = BackgroundLight
    ) { padding ->
        Column(
            Modifier
                .fillMaxSize()
                .padding(padding)
                .verticalScroll(rememberScrollState())
                .padding(16.dp)
        ) {
            uiState.deletionMessage?.let { msg ->
                Card(
                    colors = CardDefaults.cardColors(containerColor = if (msg.contains("cancelled") || msg.contains("scheduled")) Success500.copy(alpha = 0.15f) else Error500.copy(alpha = 0.1f)),
                    shape = RoundedCornerShape(12.dp),
                    modifier = Modifier.fillMaxWidth().padding(bottom = 12.dp)
                ) {
                    Text(msg, modifier = Modifier.padding(16.dp), style = MaterialTheme.typography.bodyMedium, color = if (msg.contains("cancelled") || msg.contains("scheduled")) Success600 else Error600)
                }
            }

            Text("Closing your account will permanently delete your profile, conversations, and all other data. Deletion is processed 6 months after you submit the request. You can cancel at any time before then.", style = MaterialTheme.typography.bodyMedium, color = TextSecondary)
            Spacer(Modifier.height(16.dp))

            if (uiState.deletionStatus?.pending == true) {
                Card(
                    colors = CardDefaults.cardColors(containerColor = Error500.copy(alpha = 0.08f)),
                    shape = RoundedCornerShape(12.dp),
                    border = androidx.compose.foundation.BorderStroke(1.dp, Error500.copy(alpha = 0.3f)),
                    modifier = Modifier.fillMaxWidth().padding(bottom = 16.dp)
                ) {
                    Column(Modifier.padding(16.dp)) {
                        Text("Deletion scheduled", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold, color = Error600)
                        Spacer(Modifier.height(4.dp))
                        Text("Your data will be removed on ${uiState.deletionStatus?.scheduledDeletionAt?.take(10) ?: "—"}. You can cancel before then.", style = MaterialTheme.typography.bodySmall, color = TextPrimary)
                    }
                }
                Button(
                    onClick = { viewModel.cancelDataDeletion() },
                    enabled = !uiState.deletionLoading,
                    modifier = Modifier.fillMaxWidth().height(48.dp),
                    shape = RoundedCornerShape(12.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = Primary500)
                ) {
                    if (uiState.deletionLoading) CircularProgressIndicator(Modifier.size(24.dp), color = MaterialTheme.colorScheme.onPrimary, strokeWidth = 2.dp)
                    else Text("Cancel deletion request")
                }
            } else {
                OutlinedButton(
                    onClick = { showConfirm = true },
                    modifier = Modifier.fillMaxWidth().height(48.dp),
                    shape = RoundedCornerShape(12.dp),
                    colors = ButtonDefaults.outlinedButtonColors(contentColor = Error600)
                ) {
                    Text("Request account closure")
                }
            }
        }
    }

    if (showConfirm) {
        AlertDialog(
            onDismissRequest = { showConfirm = false },
            title = { Text("Request account closure?") },
            text = { Text("Your data will be permanently deleted 6 months from today. You may cancel this request at any time before then from this page.") },
            confirmButton = {
                Button(
                    onClick = {
                        viewModel.requestDataDeletion()
                        showConfirm = false
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = Error600)
                ) { Text("Yes, request closure") }
            },
            dismissButton = { TextButton(onClick = { showConfirm = false }) { Text("Cancel") } }
        )
    }
}
