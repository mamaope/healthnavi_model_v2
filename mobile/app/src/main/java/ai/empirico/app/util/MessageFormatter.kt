package ai.empirico.app.util

import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.unit.sp
import com.google.gson.Gson
import com.google.gson.JsonObject
import com.google.gson.JsonParser
import ai.empirico.app.ui.theme.Primary500
import ai.empirico.app.ui.theme.TextPrimary
import ai.empirico.app.ui.theme.Gray100

/**
 * Formats AI responses similar to the frontend implementation.
 * Handles markdown formatting, JSON responses, and medical-specific enhancements.
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
                appendLine()
                append(overview)
                appendLine()
                appendLine()
            }
            
            // Differential Diagnoses
            json.get("differential_diagnoses")?.asJsonArray?.let { diagnoses ->
                if (diagnoses.size() > 0) {
                    addHeading("🔍 Differential Diagnoses")
                    appendLine()
                    diagnoses.forEach { item ->
                        item.asJsonObject.let { diag ->
                            val diagnosis = diag.get("diagnosis")?.asString ?: "Diagnosis"
                            val probability = diag.get("probability_percent")?.asInt
                            val evidence = diag.get("evidence")?.asString
                            
                            append("• ")
                            pushStyle(SpanStyle(fontWeight = FontWeight.Bold))
                            append(diagnosis)
                            pop()
                            if (probability != null) {
                                append(" (")
                                pushStyle(SpanStyle(color = Primary500))
                                append("$probability%")
                                pop()
                                append(")")
                            }
                            appendLine()
                            if (evidence != null) {
                                pushStyle(SpanStyle(fontStyle = FontStyle.Italic))
                                append("  $evidence")
                                pop()
                                appendLine()
                            }
                        }
                    }
                    appendLine()
                }
            }
            
            // Immediate Workup
            json.get("immediate_workup")?.asJsonArray?.let { workup ->
                if (workup.size() > 0) {
                    addHeading("🔬 Immediate Workup & Investigations")
                    appendLine()
                    workup.forEach { item ->
                        append("• ${item.asString}")
                        appendLine()
                    }
                    appendLine()
                }
            }
            
            // Management
            json.get("management")?.asJsonArray?.let { management ->
                if (management.size() > 0) {
                    addHeading("💊 Management & Recommendations")
                    appendLine()
                    management.forEach { item ->
                        append("• ${item.asString}")
                        appendLine()
                    }
                    appendLine()
                }
            }
            
            // Additional Information
            json.get("additional_information_needed")?.asString?.let { info ->
                addHeading("ℹ️ Additional Information Needed")
                appendLine()
                append(info)
                appendLine()
                appendLine()
            }
            
            // Sources
            json.get("sources_used")?.asJsonArray?.let { sources ->
                if (sources.size() > 0) {
                    addHeading("📚 Sources")
                    appendLine()
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
        // Decode HTML entities
        var processed = ai.empirico.app.util.MessageFormatter.decodeHtmlEntities(markdown)
        
        // Fix markdown spacing
        processed = ai.empirico.app.util.MessageFormatter.fixMarkdownSpacing(processed)
        
        // Convert **BOLD HEADINGS** to proper headings
        processed = ai.empirico.app.util.MessageFormatter.convertBoldHeadings(processed)
        
        // Clean up multiple blank lines
        processed = processed.replace(Regex("\n{3,}"), "\n\n")
        processed = processed.replace(Regex("^\n+"), "")
        
        // Parse markdown to AnnotatedString
        return ai.empirico.app.util.MessageFormatter.parseMarkdown(processed)
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
     * Fixes markdown spacing issues
     */
    private fun fixMarkdownSpacing(markdown: String): String {
        var fixed = markdown
        
        // Strip closing ## from headings
        fixed = fixed.replace(Regex("(#{1,6})\\s+([\\s\\S]+?)\\s+\\1\\s*$", RegexOption.MULTILINE), "$1 $2")
        
        // Add blank lines before headings
        fixed = fixed.replace(Regex("([^\\n])\\n(#{1,6}\\s)"), "$1\n\n$2")
        
        // Add blank lines between consecutive headings
        fixed = fixed.replace(Regex("(#{1,6}\\s[^\\n]+)\\n(#{1,6}\\s)"), "$1\n\n$2")
        
        // Add blank line after heading if followed by content
        fixed = fixed.replace(Regex("(#{1,6}[^\\n]+)\\n([^#\\n])"), "$1\n\n$2")
        
        // Add blank lines before lists
        fixed = fixed.replace(Regex("([^\\n])\\n(\\d+\\.\\s)"), "$1\n\n$2")
        fixed = fixed.replace(Regex("([^\\n])\\n([-*]\\s)"), "$1\n\n$2")
        
        return fixed
    }
    
    /**
     * Converts **BOLD HEADINGS** to proper markdown headings
     */
    private fun convertBoldHeadings(text: String): String {
        val sectionHeadings = listOf(
            "CLINICAL OVERVIEW",
            "DIFFERENTIAL DIAGNOSIS",
            "DIFFERENTIAL DIAGNOSES",
            "IMMEDIATE WORKUP & INVESTIGATIONS",
            "MANAGEMENT & RECOMMENDATIONS",
            "RED FLAGS / DANGER SIGNS",
            "ADDITIONAL INFORMATION NEEDED",
            "SOURCES"
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
    private fun parseMarkdown(markdown: String): AnnotatedString {
        return buildAnnotatedString {
            val lines = markdown.lines()
            var i = 0
            var lastWasParagraph = false
            var lastWasBlank = false
            var isFirstElement = true // Track if this is the first element (no top spacing)
            
            while (i < lines.size) {
                val line = lines[i]
                
                when {
                    // Headings
                    line.matches(Regex("^#{1,6}\\s+.+")) -> {
                        // Add spacing before heading (0.75em = ~1 line) unless it's the first element
                        if (!isFirstElement) {
                            if (lastWasParagraph || lastWasBlank) {
                                appendLine() // Spacing before heading
                            } else {
                                // Even if not coming from paragraph/blank, add spacing for consistency
                                appendLine()
                            }
                        }
                        
                        val level = line.takeWhile { it == '#' }.length
                        val text = line.substringAfter("#").trim()
                        val (emoji, headingText) = ai.empirico.app.util.MessageFormatter.extractEmoji(
                            text
                        )
                        
                        addHeading(emoji + headingText, level)
                        appendLine()
                        lastWasParagraph = false
                        lastWasBlank = false
                        isFirstElement = false
                        i++
                    }
                    
                    // Unordered lists
                    line.matches(Regex("^[-*]\\s+.+")) -> {
                        if (!isFirstElement && (lastWasParagraph || lastWasBlank)) {
                            appendLine() // Single line break before list
                        }
                        val content = line.substringAfter("- ").substringAfter("* ").trim()
                        append("• ")
                        appendFormattedText(content)
                        appendLine()
                        lastWasParagraph = false
                        lastWasBlank = false
                        isFirstElement = false
                        i++
                    }
                    
                    // Ordered lists
                    line.matches(Regex("^\\d+\\.\\s+.+")) -> {
                        if (!isFirstElement && (lastWasParagraph || lastWasBlank)) {
                            appendLine() // Single line break before list
                        }
                        val match = Regex("^(\\d+)\\.\\s+(.+)").find(line)
                        if (match != null) {
                            val number = match.groupValues[1]
                            val content = match.groupValues[2]
                            append("$number. ")
                            appendFormattedText(content)
                            appendLine()
                        }
                        lastWasParagraph = false
                        lastWasBlank = false
                        isFirstElement = false
                        i++
                    }
                    
                    // Blockquotes
                    line.startsWith("> ") -> {
                        if (!isFirstElement && (lastWasParagraph || lastWasBlank)) {
                            appendLine() // Single line break before blockquote
                        }
                        val quote = line.substringAfter("> ").trim()
                        pushStyle(SpanStyle(
                            fontStyle = FontStyle.Italic,
                            background = Gray100,
                            color = TextPrimary
                        ))
                        append("💬 $quote")
                        pop()
                        appendLine()
                        lastWasParagraph = false
                        lastWasBlank = false
                        isFirstElement = false
                        i++
                    }
                    
                    // Code blocks (simple detection)
                    line.startsWith("```") -> {
                        if (!isFirstElement && (lastWasParagraph || lastWasBlank)) {
                            appendLine() // Single line break before code block
                        }
                        val language = line.substringAfter("```").trim()
                        i++
                        val codeLines = mutableListOf<String>()
                        while (i < lines.size && !lines[i].startsWith("```")) {
                            codeLines.add(lines[i])
                            i++
                        }
                        if (i < lines.size) i++ // Skip closing ```
                        
                        pushStyle(SpanStyle(
                            fontFamily = FontFamily.Monospace,
                            background = Gray100,
                            color = TextPrimary
                        ))
                        append(codeLines.joinToString("\n"))
                        pop()
                        appendLine()
                        lastWasParagraph = false
                        lastWasBlank = false
                        isFirstElement = false
                    }
                    
                    // Horizontal rule
                    line.matches(Regex("^[-*_]{3,}$")) -> {
                        if (!isFirstElement) {
                            appendLine()
                        }
                        append("─".repeat(20))
                        appendLine()
                        lastWasParagraph = false
                        lastWasBlank = false
                        isFirstElement = false
                        i++
                    }
                    
                    // Regular paragraph
                    else -> {
                        if (line.isNotBlank()) {
                            // If this starts a new paragraph (after a blank line), add single spacing
                            if (lastWasBlank && lastWasParagraph) {
                                appendLine() // Single line break between paragraphs (matches web view spacing)
                            }
                            
                            // Append the paragraph line
                            appendFormattedText(line)
                            
                            // Check what comes next
                            val nextLine = if (i + 1 < lines.size) lines[i + 1] else ""
                            
                            if (nextLine.isBlank()) {
                                // Next is blank line - end of paragraph
                                // Don't add newline here - the blank line itself provides spacing
                                // We'll add spacing when we process the next paragraph
                            } else if (nextLine.matches(Regex("^#{1,6}\\s+.+")) ||
                                      nextLine.matches(Regex("^[-*]\\s+.+")) ||
                                      nextLine.matches(Regex("^\\d+\\.\\s+.+")) ||
                                      nextLine.startsWith("> ") ||
                                      nextLine.startsWith("```") ||
                                      nextLine.matches(Regex("^[-*_]{3,}$"))) {
                                // Next is special element - end of paragraph, add one newline
                                appendLine()
                            } else {
                                // Next line is continuation of same paragraph - add space, no newline
                                append(" ")
                            }
                            
                            lastWasParagraph = true
                            lastWasBlank = false
                            isFirstElement = false
                        } else {
                            // Blank line - paragraph separator, don't add anything here
                            // The spacing will be added when we process the next paragraph
                            if (lastWasParagraph) {
                                lastWasBlank = true
                            }
                            // Don't append anything for blank lines
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
     * Appends formatted text (handles bold, italic, inline code, links)
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
            
            val matches = listOfNotNull(
                boldMatch?.let { Triple(it.range.first, it.range.last, "bold") },
                italicMatch?.let { Triple(it.range.first, it.range.last, "italic") },
                codeMatch?.let { Triple(it.range.first, it.range.last, "code") },
                linkMatch?.let { Triple(it.range.first, it.range.last, "link") }
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
                        background = Gray100,
                        color = TextPrimary
                    ))
                    append(content)
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
            }
            
            position = end + 1
        }
    }
    
    /**
     * Adds a heading with appropriate styling matching web view
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
        
        // All headings use primary color (teal) matching web view
        pushStyle(SpanStyle(
            fontSize = fontSize,
            fontWeight = FontWeight.SemiBold, // 600 weight
            color = Primary500 // Use theme primary color (teal) instead of blue
        ))
        append(text)
        pop()
        
        // Add spacing after heading (matching web view margin-bottom)
        appendLine()
    }
}

