package com.mamaope.healthnavy.util

import androidx.compose.ui.graphics.Color
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

/**
 * Formats AI responses similar to the frontend implementation.
 * Handles markdown formatting, JSON responses, and medical-specific enhancements.
 */
object MessageFormatter {
    
    private val gson = Gson()
    
    /**
     * Main entry point for formatting AI responses
     */
    fun formatMessage(content: String): AnnotatedString {
        if (content.isBlank()) return AnnotatedString("")
        
        val trimmed = content.trim()
        
        // Check if it's a JSON response
        if (trimmed.startsWith("{") && trimmed.endsWith("}")) {
            try {
                val json = JsonParser.parseString(trimmed).asJsonObject
                val formatted = formatClinicalJson(json)
                if (formatted.isNotEmpty()) {
                    return formatted
                }
            } catch (e: Exception) {
                // Fall back to markdown renderer
            }
        }
        
        // Check if it contains differential diagnosis pattern
        if (trimmed.contains("**DIFFERENTIAL DIAGNOSIS**", ignoreCase = true)) {
            return formatMarkdown(trimmed)
        }
        
        // Use enhanced markdown formatter
        return formatMarkdown(trimmed)
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
                                pushStyle(SpanStyle(color = Color(0xFF1976D2)))
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
        var processed = decodeHtmlEntities(markdown)
        
        // Fix markdown spacing
        processed = fixMarkdownSpacing(processed)
        
        // Convert **BOLD HEADINGS** to proper headings
        processed = convertBoldHeadings(processed)
        
        // Clean up multiple blank lines
        processed = processed.replace(Regex("\n{3,}"), "\n\n")
        processed = processed.replace(Regex("^\n+"), "")
        
        // Parse markdown to AnnotatedString
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
            
            while (i < lines.size) {
                val line = lines[i]
                
                when {
                    // Headings
                    line.matches(Regex("^#{1,6}\\s+.+")) -> {
                        val level = line.takeWhile { it == '#' }.length
                        val text = line.substringAfter("#").trim()
                        val (emoji, headingText) = extractEmoji(text)
                        
                        appendLine()
                        addHeading(emoji + headingText, level)
                        appendLine()
                        i++
                    }
                    
                    // Unordered lists
                    line.matches(Regex("^[-*]\\s+.+")) -> {
                        val content = line.substringAfter("- ").substringAfter("* ").trim()
                        append("• ")
                        appendFormattedText(content)
                        appendLine()
                        i++
                    }
                    
                    // Ordered lists
                    line.matches(Regex("^\\d+\\.\\s+.+")) -> {
                        val match = Regex("^(\\d+)\\.\\s+(.+)").find(line)
                        if (match != null) {
                            val number = match.groupValues[1]
                            val content = match.groupValues[2]
                            append("$number. ")
                            appendFormattedText(content)
                            appendLine()
                        }
                        i++
                    }
                    
                    // Blockquotes
                    line.startsWith("> ") -> {
                        val quote = line.substringAfter("> ").trim()
                        pushStyle(SpanStyle(
                            fontStyle = FontStyle.Italic,
                            background = Color(0xFFF5F5F5)
                        ))
                        append("💬 $quote")
                        pop()
                        appendLine()
                        i++
                    }
                    
                    // Code blocks (simple detection)
                    line.startsWith("```") -> {
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
                            background = Color(0xFFF5F5F5)
                        ))
                        append(codeLines.joinToString("\n"))
                        pop()
                        appendLine()
                    }
                    
                    // Horizontal rule
                    line.matches(Regex("^[-*_]{3,}$")) -> {
                        appendLine()
                        append("─".repeat(20))
                        appendLine()
                        i++
                    }
                    
                    // Regular paragraph
                    else -> {
                        if (line.isNotBlank()) {
                            appendFormattedText(line)
                            appendLine()
                        } else {
                            appendLine()
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
                        background = Color(0xFFF5F5F5)
                    ))
                    append(content)
                    pop()
                }
                "link" -> {
                    val linkText = linkMatch!!.groupValues[1]
                    val url = linkMatch.groupValues[2]
                    pushStyle(SpanStyle(
                        color = Color(0xFF1976D2),
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
     * Adds a heading with appropriate styling
     */
    private fun AnnotatedString.Builder.addHeading(text: String, level: Int = 2) {
        val fontSize = when (level) {
            1 -> 24.sp
            2 -> 20.sp
            3 -> 18.sp
            4 -> 16.sp
            5 -> 14.sp
            6 -> 12.sp
            else -> 20.sp
        }
        
        pushStyle(SpanStyle(
            fontSize = fontSize,
            fontWeight = FontWeight.Bold,
            color = Color(0xFF1976D2)
        ))
        append(text)
        pop()
    }
}

