package ai.empirico.app.util

import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.ParagraphStyle
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.style.TextIndent
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.unit.sp
import com.google.gson.Gson
import com.google.gson.JsonObject
import com.google.gson.JsonParser
import java.util.regex.Pattern
import ai.empirico.app.ui.theme.Primary500
import ai.empirico.app.ui.theme.TextPrimary
import ai.empirico.app.ui.theme.Gray100
import ai.empirico.app.ui.theme.CodeBlockBackground
import ai.empirico.app.ui.theme.BorderLight

/**
 * Formats AI responses for readability. Uses:
 * - WCAG‑aligned spacing: line height ≥1.5× font (handled in ChatScreen), clear
 *   block separation via fixMarkdownSpacing and parseMarkdown.
 * - Consistent end-of-paragraph: newline when followed by blank, heading, list,
 *   blockquote, code, or rule.
 * - One blank above headings (except first), one blank below; one blank before
 *   lists and blockquotes, after lists and blockquotes.
 */
object MessageFormatter {
    
    private val gson = Gson()
    
    /**
     * Main entry point for formatting AI responses
     */
    fun formatMessage(content: String?): AnnotatedString {
        if (content.isNullOrBlank()) return AnnotatedString("")
        
        val trimmed = content.trim()
        
        // Check if it's a JSON response
        if (trimmed.startsWith("{") && trimmed.endsWith("}")) {
            try {
                val json = JsonParser.parseString(trimmed).asJsonObject
                val formatted = ai.empirico.app.util.MessageFormatter.formatClinicalJson(json)
                if (formatted.isNotEmpty()) {
                    return formatted
                }
            } catch (e: Exception) {
                // Fall back to markdown renderer
            }
        }
        
        // Check if it contains differential diagnosis pattern
        if (trimmed.contains("**DIFFERENTIAL DIAGNOSIS**", ignoreCase = true)) {
            return ai.empirico.app.util.MessageFormatter.formatMarkdown(trimmed)
        }
        
        // Use enhanced markdown formatter
        return ai.empirico.app.util.MessageFormatter.formatMarkdown(trimmed)
    }
    
    /**
     * Formats clinical JSON responses
     */
    private fun formatClinicalJson(json: JsonObject): AnnotatedString {
        return buildAnnotatedString {
            // Clinical Overview
            json.get("clinical_overview")?.asString?.let { overview ->
                addHeading("🏥 Clinical Overview")
                append(" ")
                append(overview)
                appendLine()
            }
            
            // Differential Diagnoses
            json.get("differential_diagnoses")?.asJsonArray?.let { diagnoses ->
                if (diagnoses.size() > 0) {
                    addHeading("🔍 Differential Diagnoses")
                    append(" ")
                    diagnoses.forEach { item ->
                        item.asJsonObject.let { diag ->
                            val diagnosis = diag.get("diagnosis")?.asString?.trim() ?: ""
                            val probability = diag.get("probability_percent")?.asInt
                            val evidence = diag.get("evidence")?.asString?.trim()
                            if (diagnosis.isBlank() && evidence.isNullOrBlank()) return@let  // Skip empty bullets
                            
                            pushStyle(ParagraphStyle(textIndent = TextIndent(restLine = 28.sp)))
                            append("    • ")
                            pushStyle(SpanStyle(fontWeight = FontWeight.Bold))
                            append(diagnosis.ifBlank { "Diagnosis" })
                            pop()
                            if (probability != null) {
                                append(" (")
                                pushStyle(SpanStyle(color = Primary500))
                                append("$probability%")
                                pop()
                                append(")")
                            }
                            appendLine()
                            pop()
                            if (evidence != null) {
                                pushStyle(SpanStyle(fontStyle = FontStyle.Italic))
                                append("  $evidence")
                                pop()
                                appendLine()
                            }
                        }
                    }
                }
            }
            
            // Immediate Workup
            json.get("immediate_workup")?.asJsonArray?.let { workup ->
                if (workup.size() > 0) {
                    addHeading("🔬 Immediate Workup & Investigations")
                    append(" ")
                    workup.forEach { item ->
                        if (item.asString.isBlank()) return@forEach
                        pushStyle(ParagraphStyle(textIndent = TextIndent(restLine = 28.sp)))
                        append("    • ${item.asString}")
                        appendLine()
                        pop()
                    }
                }
            }
            
            // Management
            json.get("management")?.asJsonArray?.let { management ->
                if (management.size() > 0) {
                    addHeading("💊 Management & Recommendations")
                    append(" ")
                    management.forEach { item ->
                        if (item.asString.isBlank()) return@forEach
                        pushStyle(ParagraphStyle(textIndent = TextIndent(restLine = 28.sp)))
                        append("    • ${item.asString}")
                        appendLine()
                        pop()
                    }
                }
            }
            
            // Additional Information
            json.get("additional_information_needed")?.asString?.let { info ->
                addHeading("ℹ️ Additional Information Needed")
                append(" ")
                append(info)
                appendLine()
            }
            
            // Sources
            json.get("sources_used")?.asJsonArray?.let { sources ->
                if (sources.size() > 0) {
                    addHeading("📚 Sources")
                    append(" ")
                    append(sources.joinToString(", ") { it.asString })
                    appendLine()
                }
            }
        }
    }
    
    /**
     * Formats markdown text with medical-specific enhancements
     */
    private fun formatMarkdown(markdown: String): AnnotatedString {
        var processed = decodeHtmlEntities(markdown)
        processed = fixMarkdownSpacing(processed)
        processed = splitRunOnHeadings(processed)
        // Fix emoji on separate line from heading (match frontend)
        processed = processed.replace(Regex("(##\\s+\\p{So})\\s*\\n\\s*([A-Z])"), "$1 $2")
        processed = convertBoldHeadings(processed)

        // Clean up multiple blank lines
        processed = processed.replace(Regex("\n{3,}"), "\n\n")
        processed = processed.replace(Regex("^\n+"), "")

        return parseMarkdown(processed)
    }
    
    /**
     * Decodes HTML entities
     */
    private fun decodeHtmlEntities(text: String): String {
        return text
            .replace("&quot;", "\"")
            .replace("&#x27;", "'")
            .replace("&amp;", "&")
            .replace("&lt;", "<")
            .replace("&gt;", ">")
            .replace("&nbsp;", " ")
    }
    
    /**
     * Fixes markdown spacing so headings, paragraphs, lists, and blockquotes
     * are clearly separated. Mirrors web frontend fixMarkdownSpacing() exactly.
     */
    private fun fixMarkdownSpacing(markdown: String): String {
        var fixed = markdown

        // CRITICAL: Strip closing ## from headings (## Heading ## → ## Heading)
        fixed = fixed.replace(Regex("(#{1,6})\\s+([\\s\\S]+?)\\s+\\1\\s*$", RegexOption.MULTILINE), "$1 $2")

        // STEP 1: If there are NO newlines at all (everything on one line)
        if (!markdown.contains("\n")) {
            fixed = fixed.replace(Regex("\\s+(##\\s)"), "\n\n$1")
            val headingTitles = listOf(
                "Clinical Overview", "Differential Diagnoses", "Immediate Workup & Investigations",
                "Immediate Workup &amp; Investigations", "Management & Recommendations",
                "Management &amp; Recommendations", "Red Flags / Danger Signs",
                "Additional Information Needed", "Sources", "Drug Overview", "Side Effects",
                "Drug Interactions", "Contraindications", "Mechanism of Action", "Chemical Information"
            )
            headingTitles.forEach { title ->
                val escaped = Pattern.quote(title)
                fixed = fixed.replace(Regex("(##\\s+[^\\s]+\\s+$escaped)\\s+-\\s+"), "$1\n\n- ")
                fixed = fixed.replace(Regex("(##\\s+[^\\s]+\\s+$escaped)\\s+([[(])"), "$1\n\n$2")
                fixed = fixed.replace(Regex("(##\\s+[^\\s]+\\s+$escaped)\\s+([A-Za-z0-9])"), "$1\n\n$2")
                fixed = fixed.replace(Regex("(##\\s+[^\\s]+\\s+$escaped)\\s+(>)"), "$1\n\n$2")
            }
            fixed = fixed.replace(Regex("(\\]\\.\\s+)(\\d+\\.\\s+\\*\\*)"), "$1\n\n$2")
            fixed = fixed.replace(Regex("([a-z]\\.\\s+)(\\d+\\.\\s+\\*\\*)"), "$1\n\n$2")
            fixed = fixed.replace(Regex("(\\)\\.\\s+)(\\d+\\.\\s+\\*\\*)"), "$1\n\n$2")
            fixed = fixed.replace(Regex("(\\]\\.\\s+)([-*]\\s+\\*\\*)"), "$1\n$2")
            fixed = fixed.replace(Regex("([a-z]\\.\\s+)([-*]\\s+\\*\\*)"), "$1\n$2")
            fixed = fixed.replace(Regex("(\\]\\.\\s+)([-*]\\s+[A-Z])"), "$1\n$2")
            fixed = fixed.replace(Regex("([a-z]\\.\\s+)([-*]\\s+[A-Z])"), "$1\n$2")
            fixed = fixed.replace(Regex("(\\)\\.\\s+)([-*]\\s+[A-Z])"), "$1\n$2")
        }

        // STEP 2: Add blank lines before ANY heading
        fixed = fixed.replace(Regex("([^\\n])\\n(#{1,6}\\s)"), "$1\n\n$2")

        // STEP 3: Add blank lines BETWEEN consecutive headings
        fixed = fixed.replace(Regex("(#{1,6}\\s[^\\n]+)\\n(#{1,6}\\s)"), "$1\n\n$2")

        // STEP 4: Add blank line after heading if followed by content
        fixed = fixed.replace(Regex("(#{1,6}[^\\n]+)\\n([^#\\n])"), "$1\n\n$2")

        // STEP 5: Add blank lines before numbered lists
        fixed = fixed.replace(Regex("([^\\n])\\n(\\d+\\.\\s)"), "$1\n\n$2")
        fixed = fixed.replace(Regex("(#{1,6}[^\\n]+)\\n(\\d+\\.\\s)"), "$1\n\n$2")

        // STEP 6: Add blank lines before bullet lists
        fixed = fixed.replace(Regex("([^\\n])\\n([-*]\\s)"), "$1\n\n$2")

        // STEP 7: Add blank line after lists (before non-list content)
        fixed = fixed.replace(Regex("(\\n(?:\\d+\\.|-|\\*)\\s[^\\n]+)\\n([^\\n\\d\\-\\*#])"), "$1\n\n$2")

        // STEP 8: Add blank lines before blockquotes
        fixed = fixed.replace(Regex("([^\\n>])\\n(>\\s)"), "$1\n\n$2")

        // STEP 9: Add blank lines after blockquotes
        fixed = fixed.replace(Regex("(>\\s[^\\n]+)\\n([^>\\n#])"), "$1\n\n$2")

        // STEP 10: Clean up any triple+ blank lines
        fixed = fixed.replace(Regex("\n{3,}"), "\n\n")

        // STEP 11: Remove blank lines at the very start
        fixed = fixed.replace(Regex("^\\n+"), "")

        return fixed
    }

    /**
     * Splits run-on text where ## appears without preceding newline (e.g. "text## Heading").
     * Must run after fixMarkdownSpacing since it handles edge cases.
     */
    private fun splitRunOnHeadings(text: String): String {
        return text.replace(Regex("([^\\n#]+)(#{1,6}\\s)"), "$1\n\n$2")
    }
    
    /** Icon mapping for headings (matches frontend markdown.ts iconMap) */
    private val iconMap = mapOf(
        "question" to "📋", "rationale" to "🧠", "impression" to "💡", "clinical impression" to "💡",
        "management" to "⚕️", "further management" to "⚕️", "sources" to "📚", "knowledge base" to "📚",
        "alert" to "🚨", "clinical overview" to "🏥", "differential diagnos" to "🔍",
        "immediate workup" to "🔬", "workup" to "🔬", "red flags" to "🚩", "treatment" to "💊",
        "medication" to "💊", "history" to "📊", "examination" to "🔬", "investigation" to "🔬",
        "assessment" to "📋", "plan" to "📝", "follow-up" to "📅", "prognosis" to "📈",
    )
    
    private fun iconForHeading(lowerText: String): String {
        for ((key, value) in iconMap) {
            if (lowerText.contains(key)) return "$value "
        }
        return ""
    }
    
    /**
     * Converts **BOLD HEADINGS** to proper markdown headings
     */
    private fun convertBoldHeadings(text: String): String {
        // Match frontend src/utils/markdown.ts sectionHeadings
        val sectionHeadings = listOf(
            "CLINICAL OVERVIEW",
            "Explanation", "Question", "Drug Interactions", "Drug-Drug Interaction",
            "Rationale", "Impression", "Conclusion", "Management Considerations",
            "Important Considerations", "Clinical Considerations", "Further Management",
            "Summary", "Differential Diagnosis", "Management", "References",
            "Investigations / Workup", "DIFFERENTIAL DIAGNOSES",
            "IMMEDIATE WORKUP & INVESTIGATIONS", "IMMEDIATE WORKUP &amp; INVESTIGATIONS",
            "MANAGEMENT & RECOMMENDATIONS", "MANAGEMENT &amp; RECOMMENDATIONS",
            "RED FLAGS / DANGER SIGNS", "RED FLAGS \\/ DANGER SIGNS",
            "ADDITIONAL INFORMATION NEEDED", "SOURCES",
            "IMPORTANT", "KEY POINTS", "RECOMMENDATIONS", "FINDINGS", "ASSESSMENT",
            "PLAN", "FOLLOW-UP", "PROGNOSIS", "NEXT STEPS", "DIAGNOSIS",
            "TREATMENT", "SYMPTOMS", "CAUSES", "PREVENTION", "NOTES"
        )
        
        var result = text
        sectionHeadings.forEach { heading ->
            val pattern = Regex("\\*\\*$heading\\*\\*", RegexOption.IGNORE_CASE)
            val titleCase = heading.lowercase().split(" ").joinToString(" ") { 
                it.replaceFirstChar { char -> char.uppercaseChar() }
            }
            result = result.replace(pattern, "\n\n## $titleCase\n\n")
        }
        return result
    }
    
    /**
     * Parses markdown to AnnotatedString
     */
    /**
     * Regex patterns for element detection (match web marked.js parsing).
     * Use trimmed lines so "  ## Heading" is detected.
     */
    private val headingRegex = Regex("^#{1,6}\\s*.+")  // # or ## etc, optional space, content
    private val boldOnlyHeadingRegex = Regex("^\\s*\\*\\*([^*]+)\\*\\*\\s*$")  // Standalone **BOLD** = heading
    private val unorderedListRegex = Regex("^[-*]\\s+.+")
    private val orderedListRegex = Regex("^\\d+\\.\\s+.+")
    private val horizontalRuleRegex = Regex("^[-*_]{3,}$")

    private fun parseMarkdown(markdown: String): AnnotatedString {
        return buildAnnotatedString {
            val lines = markdown.lines()
            var i = 0
            var lastWasParagraph = false
            var lastWasBlank = false
            var lastWasList = false
            var lastWasBlockquote = false
            var lastWasHeading = false
            var isFirstElement = true
            
            while (i < lines.size) {
                val rawLine = lines[i]
                val line = rawLine.trim()  // Trim for detection (web/marked normalizes whitespace)
                
                when {
                    // Headings — strip ## markers, render as styled heading (match web: marked.parse → h2)
                    line.matches(headingRegex) -> {
                        val level = line.takeWhile { it == '#' }.length
                        if (!isFirstElement) appendLine()  // Newline before every heading (except first)
                        val text = line.drop(level).trim()
                        if (text.isNotEmpty()) {
                            val (emoji, headingText) = extractEmoji(text)
                            val prefix = if (emoji.isNotEmpty()) emoji else iconForHeading(headingText.lowercase())
                            
                            addHeading(prefix + headingText, level)
                        }
                        lastWasParagraph = false
                        lastWasBlank = false
                        lastWasList = false
                        lastWasBlockquote = false
                        lastWasHeading = true
                        isFirstElement = false
                        i++
                    }
                    
                    // Unordered lists — newline before when not after paragraph/list; space after heading
                    line.matches(unorderedListRegex) -> {
                        val content = line.substringAfter("- ").substringAfter("* ").trim()
                        if (content.isNotBlank()) {
                            when {
                                !isFirstElement && !lastWasParagraph && !lastWasList && !lastWasHeading -> appendLine()
                                lastWasHeading -> append(" ")
                                else -> { /* no separator */ }
                            }
                            pushStyle(ParagraphStyle(textIndent = TextIndent(restLine = 28.sp)))  // Align wrapped content with text after bullet
                            append("    • ")  // 2em indent (match web ul/ol padding-left: 2em)
                            appendFormattedText(content)
                            appendLine()
                            pop()
                            lastWasParagraph = false
                            lastWasBlank = false
                            lastWasList = true
                            lastWasBlockquote = false
                            lastWasHeading = false
                            isFirstElement = false
                        }
                        i++
                    }
                    
                    // Ordered lists — newline before when not after paragraph/list; space after heading
                    line.matches(orderedListRegex) -> {
                        val match = Regex("^(\\d+)\\.\\s+(.+)").find(line)
                        if (match != null) {
                            val number = match.groupValues[1]
                            val content = match.groupValues[2].trim()
                            if (content.isNotBlank()) {
                                when {
                                    !isFirstElement && !lastWasParagraph && !lastWasList && !lastWasHeading -> appendLine()
                                    lastWasHeading -> append(" ")
                                    else -> { /* no separator */ }
                                }
                                pushStyle(ParagraphStyle(textIndent = TextIndent(restLine = 32.sp)))  // Align wrapped content (wider for "1. " etc)
                                append("    $number. ")  // 2em indent (match web ul/ol padding-left: 2em)
                                appendFormattedText(content)
                                appendLine()
                                pop()
                                lastWasParagraph = false
                                lastWasBlank = false
                                lastWasList = true
                                lastWasBlockquote = false
                                lastWasHeading = false
                                isFirstElement = false
                            }
                        }
                        i++
                    }
                    
                    // Standalone **BOLD** lines — treat as heading (AI often uses these without ##)
                    line.matches(boldOnlyHeadingRegex) -> {
                        if (!isFirstElement) appendLine()  // Newline before every heading (except first)
                        val match = boldOnlyHeadingRegex.find(line)
                        if (match != null) {
                            val headingText = match.groupValues[1].trim()
                            if (headingText.isNotEmpty()) {
                                val prefix = iconForHeading(headingText.lowercase())
                                addHeading(prefix + headingText, 2)
                            }
                        }
                        lastWasParagraph = false
                        lastWasBlank = false
                        lastWasList = false
                        lastWasBlockquote = false
                        lastWasHeading = true
                        isFirstElement = false
                        i++
                    }
                    
                    // Blockquotes — newline before when not after paragraph/consecutive; space after heading
                    line.startsWith(">") -> {
                        when {
                            !isFirstElement && !lastWasBlockquote && !lastWasParagraph && !lastWasHeading -> appendLine()
                            lastWasHeading -> append(" ")
                            else -> { /* no separator */ }
                        }
                        val quote = line.substringAfter(">").trim()
                        val lower = quote.lowercase()
                        val icon = when {
                            lower.contains("note:") || lower.contains("📝") -> "📝"
                            lower.contains("warning:") || lower.contains("⚠️") -> "⚠️"
                            lower.contains("tip:") || lower.contains("💡") -> "💡"
                            lower.contains("important:") || lower.contains("❗") -> "❗"
                            else -> "💬"
                        }
                        pushStyle(SpanStyle(
                            fontStyle = FontStyle.Italic,
                            background = Primary500.copy(alpha = 0.07f),
                            color = TextPrimary
                        ))
                        append(" ▌ $icon $quote ")  // ▌ simulates border-left 4px
                        pop()
                        appendLine()
                        lastWasParagraph = false
                        lastWasBlank = false
                        lastWasList = false
                        lastWasBlockquote = true
                        lastWasHeading = false
                        isFirstElement = false
                        i++
                    }
                    
                    // Code blocks (simple detection)
                    line.startsWith("```") -> {
                        when {
                            !isFirstElement && !lastWasParagraph && !lastWasHeading -> appendLine()
                            lastWasHeading -> append(" ")
                            else -> { /* no separator */ }
                        }
                        val language = line.substringAfter("```").trim()
                        i++
                        val codeLines = mutableListOf<String>()
                        while (i < lines.size && !lines[i].startsWith("```")) {
                            codeLines.add(lines[i])
                            i++
                        }
                        if (i < lines.size) i++ // Skip closing ```
                        
                        val padded = codeLines.joinToString("\n") { "  $it" }
                        pushStyle(SpanStyle(
                            fontFamily = FontFamily.Monospace,
                            fontSize = 13.sp,
                            background = CodeBlockBackground,
                            color = TextPrimary
                        ))
                        append("  $padded")
                        pop()
                        appendLine()
                        lastWasParagraph = false
                        lastWasBlank = false
                        lastWasList = false
                        lastWasBlockquote = false
                        lastWasHeading = false
                        isFirstElement = false
                    }
                    
                    // Horizontal rule
                    line.matches(horizontalRuleRegex) -> {
                        if (!isFirstElement && !lastWasParagraph) appendLine()
                        pushStyle(SpanStyle(color = TextPrimary.copy(alpha = 0.35f)))
                        append("─".repeat(24))
                        pop()
                        appendLine()
                        lastWasParagraph = false
                        lastWasBlank = false
                        lastWasList = false
                        lastWasBlockquote = false
                        lastWasHeading = false
                        isFirstElement = false
                        i++
                    }
                    
                    // Regular paragraph — ensure clean end-of-paragraph and spacing (WCAG-style)
                    else -> {
                        if (rawLine.isNotBlank()) {
                            // Newline above when coming from list; space after heading (no newline)
                            if (lastWasList) appendLine()
                            else if (lastWasHeading) append(" ")
                            lastWasList = false
                            lastWasBlockquote = false
                            lastWasHeading = false
                            
                            appendFormattedText(line)
                            
                            val nextRaw = if (i + 1 < lines.size) lines[i + 1] else ""
                            val nextLine = nextRaw.trim()
                            
                            when {
                                nextRaw.isBlank() ->
                                    append(" ") // No newline between paragraphs — join with space
                                nextLine.matches(headingRegex) ||
                                    nextLine.matches(boldOnlyHeadingRegex) ||
                                    nextLine.matches(unorderedListRegex) ||
                                    nextLine.matches(orderedListRegex) ||
                                    nextLine.startsWith(">") ||
                                    nextLine.startsWith("```") ||
                                    nextLine.matches(horizontalRuleRegex) ->
                                    appendLine() // End of paragraph before heading, list, blockquote, code, rule
                                else ->
                                    append(" ") // Same paragraph continues
                            }
                            
                            lastWasParagraph = true
                            lastWasBlank = false
                            isFirstElement = false
                        } else {
                            if (lastWasParagraph) lastWasBlank = true
                        }
                        i++
                    }
                }
            }
        }
    }
    
    /**
     * Extracts emoji from text if present
     */
    private fun extractEmoji(text: String): Pair<String, String> {
        if (text.isEmpty()) {
            return Pair("", text)
        }
        
        // Check if first character is an emoji
        val firstChar = text[0]
        val codePoint = firstChar.code
        
        // Check for single-unit emoji (2600-26FF: Miscellaneous Symbols)
        if (codePoint in 0x2600..0x26FF) {
            val rest = text.substring(1).trim()
            return Pair("$firstChar ", rest)
        }
        
        // Check for surrogate pair emoji (supplementary planes like 1F300-1F9FF)
        // These are represented as two UTF-16 code units
        if (text.length > 1) {
            val secondChar = text[1]
            val highSurrogate = codePoint
            val lowSurrogate = secondChar.code
            
            // Check if it's a valid surrogate pair
            // High surrogates: D800-DBFF, Low surrogates: DC00-DFFF
            if (highSurrogate in 0xD800..0xDBFF && lowSurrogate in 0xDC00..0xDFFF) {
                // Calculate the actual Unicode code point
                val codePointValue = 0x10000 + ((highSurrogate - 0xD800) shl 10) + (lowSurrogate - 0xDC00)
                // Check if it's in common emoji ranges (1F300-1F9FF, 1F600-1F64F, etc.)
                if (codePointValue in 0x1F300..0x1F9FF || 
                    codePointValue in 0x1F600..0x1F64F ||
                    codePointValue in 0x1F900..0x1F9FF) {
                    val rest = text.substring(2).trim()
                    return Pair("${text.substring(0, 2)} ", rest)
                }
            }
        }
        
        // No emoji found
        return Pair("", text)
    }
    
    /**
     * Appends formatted text (handles bold, italic, inline code, links, probability-badge, medical-value)
     */
    private fun AnnotatedString.Builder.appendFormattedText(text: String) {
        var remaining = text
        var position = 0
        
        while (position < remaining.length) {
            // Bold **text**
            val boldMatch = Regex("\\*\\*([^*]+)\\*\\*").find(remaining, position)
            // Italic *text* or _text_
            val italicMatch = Regex("(?:\\*|_)([^*_]+)(?:\\*|_)").find(remaining, position)
            // Inline code `code`
            val codeMatch = Regex("`([^`]+)`").find(remaining, position)
            // Links [text](url)
            val linkMatch = Regex("\\[([^\\]]+)\\]\\(([^)]+)\\)").find(remaining, position)
            // Probability badge (e.g. 85%, 12.5%) - match web .probability-badge
            val probMatch = Regex("(\\d+(?:\\.\\d+)?%)").find(remaining, position)
            // Medical value (e.g. 120/80 mmHg, 38.5°C) - match web .medical-value
            val medicalMatch = Regex("(\\d+/\\d+\\s*(?:mmHg|mg/dL|g/dL|mEq/L)|\\d+(?:\\.\\d+)?°[CF])").find(remaining, position)
            
            val matches = listOfNotNull(
                boldMatch?.let { Triple(it.range.first, it.range.last, "bold") },
                italicMatch?.let { Triple(it.range.first, it.range.last, "italic") },
                codeMatch?.let { Triple(it.range.first, it.range.last, "code") },
                linkMatch?.let { Triple(it.range.first, it.range.last, "link") },
                probMatch?.let { Triple(it.range.first, it.range.last, "probability") },
                medicalMatch?.let { Triple(it.range.first, it.range.last, "medical") }
            ).sortedBy { it.first }
            
            if (matches.isEmpty()) {
                // No more formatting, append rest
                append(remaining.substring(position))
                break
            }
            
            val (start, end, type) = matches.first()
            
            // Append text before match
            if (start > position) {
                append(remaining.substring(position, start))
            }
            
            // Handle the match
            when (type) {
                "bold" -> {
                    val content = boldMatch!!.groupValues[1]
                    pushStyle(SpanStyle(fontWeight = FontWeight.Bold))
                    append(content)
                    pop()
                }
                "italic" -> {
                    val content = italicMatch!!.groupValues[1]
                    pushStyle(SpanStyle(fontStyle = FontStyle.Italic))
                    append(content)
                    pop()
                }
                "code" -> {
                    val content = codeMatch!!.groupValues[1]
                    pushStyle(SpanStyle(
                        fontFamily = FontFamily.Monospace,
                        fontSize = 13.sp,
                        background = CodeBlockBackground,
                        color = TextPrimary
                    ))
                    append(" $content ")
                    pop()
                }
                "link" -> {
                    val linkText = linkMatch!!.groupValues[1]
                    val url = linkMatch.groupValues[2]
                    pushStyle(SpanStyle(
                        color = Primary500,
                        textDecoration = TextDecoration.Underline
                    ))
                    append(linkText)
                    pop()
                }
                "probability" -> {
                    val content = probMatch!!.groupValues[1]
                    pushStyle(SpanStyle(
                        fontSize = 12.sp,
                        fontWeight = FontWeight.SemiBold,
                        color = TextPrimary
                    ))
                    append(content)
                    pop()
                }
                "medical" -> {
                    val content = medicalMatch!!.groupValues[1]
                    pushStyle(SpanStyle(
                        fontSize = 13.sp,
                        color = TextPrimary
                    ))
                    append(content)
                    pop()
                }
            }
            
            position = end + 1
        }
    }
    
    /**
     * Adds a heading with appropriate styling matching web view
     * Web: h1/h2 have border-bottom 2px; margin 0.75em; padding-bottom 0.5em; line-height 1.3
     */
    private fun AnnotatedString.Builder.addHeading(text: String, level: Int = 2) {
        // Match web view font sizes (converted from em to sp)
        // Web: h1=1.75em, h2=1.5em, h3=1.3em, h4=1.15em, h5=1.1em, h6=1em
        // Base font size is ~14px, so 1em ≈ 14sp
        val fontSize = when (level) {
            1 -> 24.5.sp  // 1.75em ≈ 24.5sp
            2 -> 21.sp    // 1.5em ≈ 21sp
            3 -> 18.2.sp  // 1.3em ≈ 18.2sp
            4 -> 16.1.sp  // 1.15em ≈ 16.1sp
            5 -> 15.4.sp  // 1.1em ≈ 15.4sp
            6 -> 14.sp    // 1em = 14sp
            else -> 21.sp
        }
        // Web: headings use line-height 1.3
        val lineHeight = (fontSize.value * 1.3f).sp
        
        pushStyle(ParagraphStyle(lineHeight = lineHeight))
        pushStyle(SpanStyle(
            fontSize = fontSize,
            fontWeight = FontWeight.SemiBold,
            color = Primary500
        ))
        append(text)
        pop()
        // H1 and H2: separator on same line (no newline after heading)
        if (level == 1 || level == 2) {
            pushStyle(SpanStyle(color = BorderLight))
            append("  " + "─".repeat(24))
            pop()
        }
        pop()  // Pop ParagraphStyle
    }
}

