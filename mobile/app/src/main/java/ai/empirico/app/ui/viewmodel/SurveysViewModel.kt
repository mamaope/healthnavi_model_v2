package ai.empirico.app.ui.viewmodel

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import ai.empirico.app.data.remote.SurveyItemDto
import ai.empirico.app.data.remote.SurveyQuestionDto
import ai.empirico.app.data.remote.SurveyQuestionsData
import ai.empirico.app.data.remote.SurveySectionDto
import ai.empirico.app.data.repository.SurveysRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class SurveysUiState(
    val surveys: List<SurveyItemDto> = emptyList(),
    val surveyData: SurveyQuestionsData? = null,
    val isLoading: Boolean = false,
    val isSubmitting: Boolean = false,
    val error: String? = null,
    val submitSuccess: Boolean = false
)

class SurveysViewModel(application: Application) : AndroidViewModel(application) {

    private val repo = SurveysRepository()

    private val _uiState = MutableStateFlow(SurveysUiState())
    val uiState: StateFlow<SurveysUiState> = _uiState.asStateFlow()

    fun loadSurveys() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            repo.getAvailableSurveys()
                .onSuccess { list -> _uiState.value = _uiState.value.copy(surveys = list, isLoading = false) }
                .onFailure { e -> _uiState.value = _uiState.value.copy(isLoading = false, error = e.message ?: "Failed to load") }
        }
    }

    fun loadSurveyQuestions(surveyType: String) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null, surveyData = null)
            repo.getSurveyQuestions(surveyType)
                .onSuccess { data -> _uiState.value = _uiState.value.copy(surveyData = data, isLoading = false) }
                .onFailure { e -> _uiState.value = _uiState.value.copy(isLoading = false, error = e.message ?: "Failed to load survey") }
        }
    }

    fun submitSurvey(surveyType: String, responses: Map<String, Any>) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isSubmitting = true, error = null, submitSuccess = false)
            repo.submitSurvey(surveyType, responses)
                .onSuccess { _uiState.value = _uiState.value.copy(isSubmitting = false, submitSuccess = true) }
                .onFailure { e -> _uiState.value = _uiState.value.copy(isSubmitting = false, error = e.message ?: "Failed to submit") }
        }
    }

    fun clearError() { _uiState.value = _uiState.value.copy(error = null) }
    fun clearSubmitSuccess() { _uiState.value = _uiState.value.copy(submitSuccess = false) }
    fun clearSurveyData() { _uiState.value = _uiState.value.copy(surveyData = null) }
}
