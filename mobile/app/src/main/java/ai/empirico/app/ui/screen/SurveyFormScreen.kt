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
import ai.empirico.app.data.remote.SurveyQuestionDto
import ai.empirico.app.ui.theme.*
import ai.empirico.app.ui.viewmodel.SurveysViewModel

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SurveyFormScreen(
    surveyType: String,
    onBack: () -> Unit,
    onSuccess: () -> Unit,
    viewModel: SurveysViewModel = viewModel()
) {
    val uiState by viewModel.uiState.collectAsState()
    var responses by remember { mutableStateOf(emptyMap<String, Any>()) }

    LaunchedEffect(surveyType) { viewModel.loadSurveyQuestions(surveyType) }
    LaunchedEffect(uiState.submitSuccess) { if (uiState.submitSuccess) { viewModel.clearSubmitSuccess(); viewModel.clearSurveyData(); onSuccess() } }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(uiState.surveyData?.title ?: "Survey", fontWeight = FontWeight.SemiBold) },
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
            uiState.error?.let { err ->
                Card(colors = CardDefaults.cardColors(containerColor = Error500.copy(alpha = 0.1f)), shape = RoundedCornerShape(12.dp), modifier = Modifier.fillMaxWidth().padding(bottom = 12.dp)) {
                    Text(err, color = Error600, modifier = Modifier.padding(16.dp), style = MaterialTheme.typography.bodyMedium)
                }
            }

            if (uiState.isLoading && uiState.surveyData == null) {
                Box(Modifier.fillMaxWidth().padding(32.dp), contentAlignment = androidx.compose.ui.Alignment.Center) {
                    CircularProgressIndicator(color = Primary500)
                }
            } else uiState.surveyData?.let { data ->
                if (data.isCompleted) {
                    Text("You have already completed this survey.", style = MaterialTheme.typography.bodyMedium, color = TextSecondary)
                } else {
                    data.sections.forEach { section ->
                        Text(section.title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Medium, color = TextPrimary, modifier = Modifier.padding(vertical = 8.dp))
                        section.questions.forEach { q -> SurveyQuestion(q, responses) { id, v -> responses = responses + (id to v) } }
                    }
                    Spacer(Modifier.height(24.dp))
                    Button(
                        onClick = { viewModel.submitSurvey(surveyType, responses) },
                        enabled = !uiState.isSubmitting,
                        modifier = Modifier.fillMaxWidth().height(48.dp),
                        shape = RoundedCornerShape(12.dp),
                        colors = ButtonDefaults.buttonColors(containerColor = Primary500)
                    ) {
                        if (uiState.isSubmitting) CircularProgressIndicator(Modifier.size(24.dp), color = MaterialTheme.colorScheme.onPrimary, strokeWidth = 2.dp)
                        else Text("Submit")
                    }
                }
            }
        }
    }
}

@Composable
private fun SurveyQuestion(q: SurveyQuestionDto, responses: Map<String, Any>, onChange: (String, Any) -> Unit) {
    Column(Modifier.padding(vertical = 6.dp)) {
        Text("${q.text}${if (q.required) " *" else ""}", style = MaterialTheme.typography.bodyMedium, color = TextPrimary)
        Spacer(Modifier.height(6.dp))
        when (q.type) {
            "text" -> OutlinedTextField(
                value = (responses[q.id] as? String) ?: "",
                onValueChange = { onChange(q.id, it) },
                modifier = Modifier.fillMaxWidth(),
                minLines = 2,
                shape = RoundedCornerShape(8.dp),
                colors = OutlinedTextFieldDefaults.colors(focusedBorderColor = Primary500, unfocusedBorderColor = BorderLight, focusedTextColor = TextPrimary, unfocusedTextColor = TextPrimary)
            )
            "single_choice" -> (q.options ?: emptyList()).forEach { opt ->
                Row(Modifier.fillMaxWidth().padding(vertical = 2.dp), verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                    RadioButton(
                        selected = (responses[q.id] as? String) == opt,
                        onClick = { onChange(q.id, opt) },
                        colors = RadioButtonDefaults.colors(selectedColor = Primary500)
                    )
                    Text(opt, style = MaterialTheme.typography.bodyMedium, color = TextPrimary, modifier = Modifier.padding(start = 8.dp))
                }
            }
            "multiple_choice" -> (q.options ?: emptyList()).forEach { opt ->
                val set = ((responses[q.id] as? List<*>) ?: emptyList<Any>()).toMutableSet()
                Row(Modifier.fillMaxWidth().padding(vertical = 2.dp), verticalAlignment = androidx.compose.ui.Alignment.CenterVertically) {
                    Checkbox(
                        checked = set.contains(opt),
                        onCheckedChange = {
                            if (it) set.add(opt) else set.remove(opt)
                            onChange(q.id, set.toList())
                        },
                        colors = CheckboxDefaults.colors(checkedColor = Primary500)
                    )
                    Text(opt, style = MaterialTheme.typography.bodyMedium, color = TextPrimary, modifier = Modifier.padding(start = 8.dp))
                }
            }
            else -> OutlinedTextField(
                value = (responses[q.id] as? String) ?: "",
                onValueChange = { onChange(q.id, it) },
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(8.dp),
                colors = OutlinedTextFieldDefaults.colors(focusedBorderColor = Primary500, unfocusedBorderColor = BorderLight, focusedTextColor = TextPrimary, unfocusedTextColor = TextPrimary)
            )
        }
    }
}
