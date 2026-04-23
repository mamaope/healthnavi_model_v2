package ai.empirico.app.ui.screen

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Star
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import ai.empirico.app.ui.theme.*

@Composable
fun FeedbackDialog(
    isOpen: Boolean,
    feedbackType: String?, // "helpful" or "not_helpful"
    onDismiss: () -> Unit,
    onSubmit: (feedbackText: String, rating: Int) -> Unit,
    isSubmitting: Boolean = false
) {
    if (!isOpen || feedbackType == null) return

    var feedbackText by remember(feedbackType) { mutableStateOf("") }
    var rating by remember(feedbackType) { mutableStateOf(0) }

    Dialog(onDismissRequest = onDismiss) {
        Card(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            shape = RoundedCornerShape(20.dp),
            colors = CardDefaults.cardColors(
                containerColor = SurfaceLight
            )
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(24.dp)
                    .verticalScroll(rememberScrollState())
            ) {
                // Header
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(
                        text = if (feedbackType == "helpful") "👍 Helpful" else "👎 Not Helpful",
                        style = MaterialTheme.typography.headlineSmall,
                        fontWeight = androidx.compose.ui.text.font.FontWeight.Bold,
                        color = TextPrimary
                    )
                    IconButton(onClick = onDismiss) {
                        Icon(
                            imageVector = Icons.Default.Close,
                            contentDescription = "Close",
                            tint = TextSecondary
                        )
                    }
                }

                Spacer(modifier = Modifier.height(24.dp))

                // Rating Section
                Text(
                    text = "Rate this response (1-5 stars) *",
                    style = MaterialTheme.typography.bodyMedium,
                    fontWeight = androidx.compose.ui.text.font.FontWeight.Medium,
                    color = TextPrimary,
                    modifier = Modifier.padding(bottom = 12.dp)
                )

                Row(
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    modifier = Modifier.padding(bottom = 16.dp)
                ) {
                    for (star in 1..5) {
                        val isFilled = star <= rating
                        IconButton(
                            onClick = { rating = star },
                            modifier = Modifier.size(40.dp)
                        ) {
                            Icon(
                                imageVector = Icons.Default.Star,
                                contentDescription = "$star stars",
                                tint = if (isFilled) Primary500 else Gray300,
                                modifier = Modifier.size(32.dp)
                            )
                        }
                    }
                }

                if (rating > 0) {
                    Text(
                        text = "$rating star${if (rating != 1) "s" else ""} selected",
                        style = MaterialTheme.typography.bodySmall,
                        color = TextSecondary,
                        modifier = Modifier.padding(bottom = 16.dp)
                    )
                }

                // Feedback Text Section
                Text(
                    text = if (feedbackType == "helpful")
                        "What made this response helpful? (Optional)"
                    else
                        "How can we improve? (Optional)",
                    style = MaterialTheme.typography.bodyMedium,
                    fontWeight = androidx.compose.ui.text.font.FontWeight.Medium,
                    color = TextPrimary,
                    modifier = Modifier.padding(bottom = 8.dp)
                )

                OutlinedTextField(
                    value = feedbackText,
                    onValueChange = { if (it.length <= 2000) feedbackText = it },
                    modifier = Modifier
                        .fillMaxWidth()
                        .heightIn(min = 100.dp, max = 200.dp),
                    placeholder = {
                        Text(
                            text = if (feedbackType == "helpful")
                                "Share what you found most useful..."
                            else
                                "Tell us what we can do better...",
                            color = TextTertiary
                        )
                    },
                    maxLines = 6,
                    shape = RoundedCornerShape(12.dp),
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedBorderColor = Primary500,
                        unfocusedBorderColor = BorderLight,
                        focusedTextColor = TextPrimary,
                        unfocusedTextColor = TextPrimary
                    )
                )

                Text(
                    text = "${feedbackText.length}/2000 characters",
                    style = MaterialTheme.typography.bodySmall,
                    color = TextTertiary,
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(top = 4.dp),
                    textAlign = androidx.compose.ui.text.style.TextAlign.End
                )

                Spacer(modifier = Modifier.height(24.dp))

                // Footer Buttons
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    OutlinedButton(
                        onClick = onDismiss,
                        modifier = Modifier.weight(1f),
                        enabled = !isSubmitting
                    ) {
                        Text("Cancel", color = TextPrimary)
                    }

                    Button(
                        onClick = {
                            onSubmit(feedbackText.trim(), rating)
                        },
                        modifier = Modifier.weight(1f),
                        enabled = !isSubmitting && rating > 0,
                        colors = ButtonDefaults.buttonColors(
                            containerColor = Primary500,
                            disabledContainerColor = Gray300
                        )
                    ) {
                        if (isSubmitting) {
                            CircularProgressIndicator(
                                modifier = Modifier.size(16.dp),
                                strokeWidth = 2.dp,
                                color = Color.White
                            )
                            Spacer(modifier = Modifier.width(8.dp))
                            Text("Submitting...", color = Color.White)
                        } else {
                            Text("Submit Feedback", color = Color.White)
                        }
                    }
                }
            }
        }
    }
}
