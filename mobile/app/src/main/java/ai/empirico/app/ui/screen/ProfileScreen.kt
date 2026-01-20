package ai.empirico.app.ui.screen

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.ArrowDropDown
import androidx.compose.material3.*
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import ai.empirico.app.ui.theme.*
import ai.empirico.app.ui.viewmodel.AuthViewModel

private val PROFESSIONAL_TYPES = listOf(
    "Consultant", "Specialist", "Senior House Officer", "Medical Officer",
    "Intern Clinician", "Other Clinical Practitioner", "Clinical/Medical Student"
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ProfileScreen(
    onBack: () -> Unit,
    viewModel: AuthViewModel = viewModel()
) {
    val uiState by viewModel.uiState.collectAsState()
    var fullName by remember { mutableStateOf(uiState.currentUser?.fullName ?: "") }
    var professionalType by remember { mutableStateOf(uiState.currentUser?.medicalProfessionalType ?: "") }
    var showPasswordDialog by remember { mutableStateOf(false) }
    var currentPw by remember { mutableStateOf("") }
    var newPw by remember { mutableStateOf("") }
    var confirmPw by remember { mutableStateOf("") }

    LaunchedEffect(uiState.currentUser) {
        fullName = uiState.currentUser?.fullName ?: ""
        professionalType = uiState.currentUser?.medicalProfessionalType ?: ""
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Profile", fontWeight = FontWeight.SemiBold) },
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
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .verticalScroll(rememberScrollState())
                .padding(16.dp)
        ) {
            uiState.profileError?.let { err ->
                Card(
                    colors = CardDefaults.cardColors(containerColor = Error500.copy(alpha = 0.1f)),
                    shape = RoundedCornerShape(12.dp),
                    modifier = Modifier.fillMaxWidth().padding(bottom = 12.dp)
                ) {
                    Text(err, color = Error600, modifier = Modifier.padding(16.dp), style = MaterialTheme.typography.bodyMedium)
                }
            }
            uiState.profileSuccess?.let { msg ->
                Card(
                    colors = CardDefaults.cardColors(containerColor = Success500.copy(alpha = 0.15f)),
                    shape = RoundedCornerShape(12.dp),
                    modifier = Modifier.fillMaxWidth().padding(bottom = 12.dp)
                ) {
                    Text(msg, color = Success600, modifier = Modifier.padding(16.dp), style = MaterialTheme.typography.bodyMedium)
                }
            }

            Text("Account", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold, color = TextPrimary)
            Spacer(Modifier.height(8.dp))
            Card(colors = CardDefaults.cardColors(containerColor = SurfaceLight), shape = RoundedCornerShape(12.dp), modifier = Modifier.fillMaxWidth()) {
                Column(Modifier.padding(16.dp)) {
                    LabelValue("Email", uiState.currentUser?.email ?: "")
                    LabelValue("Username", uiState.currentUser?.username ?: "")
                    LabelValue("Role", uiState.currentUser?.role ?: "user")
                }
            }

            Spacer(Modifier.height(24.dp))
            Text("Edit profile", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold, color = TextPrimary)
            Spacer(Modifier.height(8.dp))
            OutlinedTextField(
                value = fullName,
                onValueChange = { fullName = it },
                label = { Text("Full name") },
                modifier = Modifier.fillMaxWidth().padding(bottom = 12.dp),
                shape = RoundedCornerShape(12.dp),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = Primary500, unfocusedBorderColor = BorderLight,
                    focusedTextColor = TextPrimary, unfocusedTextColor = TextPrimary
                )
            )
            var showProTypePicker by remember { mutableStateOf(false) }
            OutlinedTextField(
                value = professionalType,
                onValueChange = {},
                readOnly = true,
                label = { Text("Professional type") },
                trailingIcon = { IconButton(onClick = { showProTypePicker = true }) { Icon(Icons.Default.ArrowDropDown, contentDescription = "Select") } },
                modifier = Modifier.fillMaxWidth().padding(bottom = 12.dp),
                shape = RoundedCornerShape(12.dp),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = Primary500, unfocusedBorderColor = BorderLight,
                    focusedTextColor = TextPrimary, unfocusedTextColor = TextPrimary
                )
            )
            if (showProTypePicker) {
                AlertDialog(
                    onDismissRequest = { showProTypePicker = false },
                    confirmButton = { TextButton(onClick = { showProTypePicker = false }) { Text("Cancel") } },
                    title = { Text("Professional type") },
                    text = {
                        Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                            PROFESSIONAL_TYPES.forEach { type ->
                                TextButton(onClick = { professionalType = type; showProTypePicker = false }) { Text(type) }
                            }
                        }
                    }
                )
            }
            Button(
                onClick = { viewModel.updateProfile(fullName.ifBlank { null }, professionalType.ifBlank { null }) },
                enabled = !uiState.profileLoading,
                modifier = Modifier.fillMaxWidth().height(48.dp),
                shape = RoundedCornerShape(12.dp),
                colors = ButtonDefaults.buttonColors(containerColor = Primary500)
            ) {
                if (uiState.profileLoading) CircularProgressIndicator(Modifier.size(24.dp), color = MaterialTheme.colorScheme.onPrimary, strokeWidth = 2.dp)
                else Text("Save changes")
            }

            Spacer(Modifier.height(24.dp))
            Text("Security", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold, color = TextPrimary)
            Spacer(Modifier.height(8.dp))
            OutlinedButton(
                onClick = { showPasswordDialog = true },
                modifier = Modifier.fillMaxWidth().height(48.dp),
                shape = RoundedCornerShape(12.dp)
            ) {
                Text("Change password")
            }
        }
    }

    if (showPasswordDialog) {
        AlertDialog(
            onDismissRequest = { showPasswordDialog = false; viewModel.clearProfileMessage() },
            title = { Text("Change password") },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    OutlinedTextField(
                        value = currentPw,
                        onValueChange = { currentPw = it },
                        label = { Text("Current password") },
                        visualTransformation = PasswordVisualTransformation(),
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(8.dp)
                    )
                    OutlinedTextField(
                        value = newPw,
                        onValueChange = { newPw = it },
                        label = { Text("New password (min 8)") },
                        visualTransformation = PasswordVisualTransformation(),
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(8.dp)
                    )
                    OutlinedTextField(
                        value = confirmPw,
                        onValueChange = { confirmPw = it },
                        label = { Text("Confirm new password") },
                        visualTransformation = PasswordVisualTransformation(),
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(8.dp)
                    )
                }
            },
            confirmButton = {
                Button(
                    onClick = {
                        if (newPw.length >= 8 && newPw == confirmPw) {
                            viewModel.changePassword(currentPw, newPw)
                            showPasswordDialog = false
                            currentPw = ""; newPw = ""; confirmPw = ""
                        }
                    }
                ) { Text("Change") }
            },
            dismissButton = { TextButton(onClick = { showPasswordDialog = false; currentPw = ""; newPw = ""; confirmPw = "" }) { Text("Cancel") } }
        )
    }
}

@Composable
private fun LabelValue(label: String, value: String) {
    Text(label, style = MaterialTheme.typography.bodySmall, color = TextSecondary)
    Text(value, style = MaterialTheme.typography.bodyMedium, color = TextPrimary, modifier = Modifier.padding(bottom = 12.dp))
}
