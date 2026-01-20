package ai.empirico.app.ui.screen

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Schedule
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import ai.empirico.app.ui.theme.*
import ai.empirico.app.ui.viewmodel.SurveysViewModel

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PilotScreen(
    onBack: () -> Unit,
    onSurveyClick: (String) -> Unit,
    viewModel: SurveysViewModel = viewModel()
) {
    val uiState by viewModel.uiState.collectAsState()

    LaunchedEffect(Unit) { viewModel.loadSurveys() }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Pilot Surveys", fontWeight = FontWeight.SemiBold) },
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
        Column(Modifier.fillMaxSize().padding(padding).padding(16.dp)) {
            uiState.error?.let { err ->
                Card(colors = CardDefaults.cardColors(containerColor = Error500.copy(alpha = 0.1f)), shape = RoundedCornerShape(12.dp), modifier = Modifier.fillMaxWidth().padding(bottom = 12.dp)) {
                    Text(err, color = Error600, modifier = Modifier.padding(16.dp), style = MaterialTheme.typography.bodyMedium)
                }
            }

            if (uiState.isLoading && uiState.surveys.isEmpty()) {
                Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    CircularProgressIndicator(color = Primary500)
                }
            } else if (uiState.surveys.isEmpty()) {
                Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Text("No surveys available", style = MaterialTheme.typography.bodyLarge, color = TextSecondary)
                }
            } else {
                Text("Complete the surveys below to help us improve.", style = MaterialTheme.typography.bodyMedium, color = TextSecondary, modifier = Modifier.padding(bottom = 12.dp))
                LazyColumn(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    items(uiState.surveys) { s ->
                        Card(
                            modifier = Modifier.fillMaxWidth().then(if (s.isCompleted) Modifier else Modifier.clickable { onSurveyClick(s.surveyType) }),
                            shape = RoundedCornerShape(12.dp),
                            colors = CardDefaults.cardColors(containerColor = SurfaceLight),
                            border = androidx.compose.foundation.BorderStroke(1.dp, BorderLight)
                        ) {
                            Column(Modifier.padding(16.dp)) {
                                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                                    Text(s.title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Medium, color = TextPrimary)
                                    if (s.isCompleted) Icon(Icons.Default.CheckCircle, contentDescription = null, modifier = Modifier.size(20.dp), tint = Success500) else Icon(Icons.Default.Schedule, contentDescription = null, modifier = Modifier.size(20.dp), tint = Warning500)
                                }
                                Text(s.description, style = MaterialTheme.typography.bodySmall, color = TextSecondary, modifier = Modifier.padding(top = 4.dp))
                                if (s.isCompleted && s.completedAt != null) Text("Completed ${s.completedAt.take(10)}", style = MaterialTheme.typography.labelSmall, color = TextTertiary, modifier = Modifier.padding(top = 4.dp))
                            }
                        }
                    }
                }
            }
        }
    }
}
