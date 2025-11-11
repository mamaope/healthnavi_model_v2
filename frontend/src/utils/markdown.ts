import { marked } from 'marked'
import DOMPurify from 'dompurify'

// ===== HTML ENTITY DECODER =====
function decodeHTMLEntities(text: string): string {
  if (typeof document === 'undefined') {
    // SSR fallback
    return text
      .replace(/&quot;/g, '"')
      .replace(/&#x27;/g, "'")
      .replace(/&amp;/g, '&')
      .replace(/&lt;/g, '<')
      .replace(/&gt;/g, '>')
  }
  const textarea = document.createElement('textarea')
  textarea.innerHTML = text
  return textarea.value
}

// ===== MARKDOWN FIXER - Add missing blank lines =====
function fixMarkdownSpacing(markdown: string): string {
  let fixed = markdown

  // CRITICAL: Strip closing ## from headings (## Heading ## → ## Heading)
  fixed = fixed.replace(/(#{1,6})\s+([\s\S]+?)\s+\1\s*$/gm, '$1 $2')

  // STEP 1: If there are NO newlines at all (everything on one line), add newlines before ## headings
  if (!markdown.includes('\n')) {
    // First, add line breaks before each ## heading
    fixed = fixed.replace(/\s+(##\s)/g, '\n\n$1')

    // Then, add line breaks after common heading patterns
    const headingTitles = [
      'Clinical Overview',
      'Differential Diagnoses',
      'Immediate Workup & Investigations',
      'Immediate Workup &amp; Investigations',
      'Management & Recommendations',
      'Management &amp; Recommendations',
      'Red Flags / Danger Signs',
      'Additional Information Needed',
      'Sources',
      'Drug Overview',
      'Side Effects',
      'Drug Interactions',
      'Contraindications',
      'Mechanism of Action',
      'Chemical Information',
    ]

    headingTitles.forEach((title) => {
      const escapedTitle = title.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

      // Match heading followed by " - " (dash with spaces for subheadings)
      const dashPattern = new RegExp(`(##\\s+[^\\s]+\\s+${escapedTitle})\\s+-\\s+`, 'g')
      fixed = fixed.replace(dashPattern, '$1\n\n- ')

      // Match heading followed by [ or ( (for citations or parentheses)
      const bracketPattern = new RegExp(`(##\\s+[^\\s]+\\s+${escapedTitle})\\s+([[(])`, 'g')
      fixed = fixed.replace(bracketPattern, '$1\n\n$2')

      // Match heading followed by capital letter, number, or lowercase letter (any content)
      const pattern = new RegExp(`(##\\s+[^\\s]+\\s+${escapedTitle})\\s+([A-Za-z0-9])`, 'g')
      fixed = fixed.replace(pattern, '$1\n\n$2')

      // Match heading followed by > (blockquote)
      const blockquotePattern = new RegExp(`(##\\s+[^\\s]+\\s+${escapedTitle})\\s+(>)`, 'g')
      fixed = fixed.replace(blockquotePattern, '$1\n\n$2')
    })

    // Add line breaks between numbered list items
    fixed = fixed.replace(/(\]\.\s+)(\d+\.\s+\*\*)/g, '$1\n\n$2')
    fixed = fixed.replace(/([a-z]\.\s+)(\d+\.\s+\*\*)/g, '$1\n\n$2')
    fixed = fixed.replace(/(\)\.\s+)(\d+\.\s+\*\*)/g, '$1\n\n$2')

    // Add line breaks between bullet list items
    fixed = fixed.replace(/(\]\.\s+)([-*]\s+\*\*)/g, '$1\n$2')
    fixed = fixed.replace(/([a-z]\.\s+)([-*]\s+\*\*)/g, '$1\n$2')

    // Handle bullet points without bold
    fixed = fixed.replace(/(\]\.\s+)([-*]\s+[A-Z])/g, '$1\n$2')
    fixed = fixed.replace(/([a-z]\.\s+)([-*]\s+[A-Z])/g, '$1\n$2')
    fixed = fixed.replace(/(\)\.\s+)([-*]\s+[A-Z])/g, '$1\n$2')
  }

  // STEP 2: Add blank lines before ANY heading
  fixed = fixed.replace(/([^\n])\n(#{1,6}\s)/g, '$1\n\n$2')

  // STEP 3: Add blank lines BETWEEN consecutive headings
  fixed = fixed.replace(/(#{1,6}\s[^\n]+)\n(#{1,6}\s)/g, '$1\n\n$2')

  // STEP 4: Add blank line after heading if followed by content
  fixed = fixed.replace(/(#{1,6}[^\n]+)\n([^#\n])/g, '$1\n\n$2')

  // STEP 5: Add blank lines before numbered lists
  fixed = fixed.replace(/([^\n])\n(\d+\.\s)/g, '$1\n\n$2')
  fixed = fixed.replace(/(#{1,6}[^\n]+)\n(\d+\.\s)/g, '$1\n\n$2')

  // STEP 6: Add blank lines before bullet lists
  fixed = fixed.replace(/([^\n])\n([-*]\s)/g, '$1\n\n$2')

  // STEP 7: Add blank line after lists (before non-list content)
  fixed = fixed.replace(/(\n(?:\d+\.|-|\*)\s[^\n]+)\n([^\n\d\-\*#])/g, '$1\n\n$2')

  // STEP 8: Add blank lines before blockquotes
  fixed = fixed.replace(/([^\n>])\n(>\s)/g, '$1\n\n$2')

  // STEP 9: Add blank lines after blockquotes
  fixed = fixed.replace(/(>\s[^\n]+)\n([^>\n#])/g, '$1\n\n$2')

  // STEP 10: Clean up any triple+ blank lines
  fixed = fixed.replace(/\n{3,}/g, '\n\n')

  // STEP 11: Remove blank lines at the very start
  fixed = fixed.replace(/^\n+/, '')

  return fixed
}

// Icon mapping for headings
const iconMap: Record<string, string> = {
  question: '📋',
  rationale: '🧠',
  impression: '💡',
  'clinical impression': '💡',
  management: '⚕️',
  'further management': '⚕️',
  sources: '📚',
  'knowledge base': '📚',
  alert: '🚨',
  'clinical overview': '🏥',
  'differential diagnos': '🔍', // Matches "diagnoses" or "diagnosis"
  'immediate workup': '🔬',
  workup: '🔬',
  'red flags': '🚩',
  treatment: '💊',
  medication: '💊',
  history: '📊',
  examination: '🔬',
  investigation: '🔬',
  assessment: '📋',
  plan: '📝',
  'follow-up': '📅',
  prognosis: '📈',
}

// Section headings to convert from **BOLD** to ## Heading
const sectionHeadings = [
  'CLINICAL OVERVIEW',
  'Explanation',
  'Question',
  'Drug Interactions',
  'Drug-Drug Interaction',
  'Rationale',
  'Impression',
  'Conclusion',
  'Management Considerations',
  'Important Considerations',
  'Clinical Considerations',
  'Further Management',
  'Summary',
  'Differential Diagnosis',
  'Management',
  'References',
  'Investigations / Workup',
  'DIFFERENTIAL DIAGNOSES',
  'IMMEDIATE WORKUP & INVESTIGATIONS',
  'IMMEDIATE WORKUP &amp; INVESTIGATIONS',
  'MANAGEMENT & RECOMMENDATIONS',
  'MANAGEMENT &amp; RECOMMENDATIONS',
  'RED FLAGS / DANGER SIGNS',
  'RED FLAGS \\/ DANGER SIGNS',
  'ADDITIONAL INFORMATION NEEDED',
  'SOURCES',
]

// Create custom renderer
const createRenderer = () => {
  const renderer = new marked.Renderer()

  // Enhanced heading renderer with medical icons
  renderer.heading = (text, level) => {
    // Check if text already has an emoji at the start
    const emojiRegex = /^[\u{1F300}-\u{1F9FF}\u{2600}-\u{26FF}]/u
    const hasEmoji = emojiRegex.test(text.trim())

    // If heading already has emoji, don't add another one
    if (hasEmoji) {
      const isAlert =
        text.toLowerCase().includes('alert') || text.toLowerCase().includes('red flag')
      const className = isAlert ? ' class="alert-heading"' : ''
      return `<h${level}${className}>${text}</h${level}>`
    }

    // Otherwise, add icon based on content
    let icon = ''
    const lowerText = text.toLowerCase()
    for (const [key, value] of Object.entries(iconMap)) {
      if (lowerText.includes(key)) {
        icon = `${value} `
        break
      }
    }

    // Add appropriate styling for alert headings
    const isAlert = lowerText.includes('alert') || lowerText.includes('red flag')
    const className = isAlert ? ' class="alert-heading"' : ''

    return `<h${level}${className}>${icon}${text}</h${level}>`
  }

  // Enhanced list renderer
  renderer.list = (body, ordered, start) => {
    const type = ordered ? 'ol' : 'ul'
    const startAttr = ordered && start !== 1 ? ` start="${start}"` : ''
    const className = ordered ? ' class="ordered-list"' : ' class="unordered-list"'
    return `<${type}${className}${startAttr}>\n${body}</${type}>\n`
  }

  // Enhanced list item renderer
  renderer.listitem = (text) => {
    const hasLeadingEmphasis =
      text.trim().startsWith('<strong>') || text.trim().startsWith('<em>')
    const className = hasLeadingEmphasis ? ' class="emphasized-item"' : ''
    return `<li${className}>${text}</li>\n`
  }

  // Enhanced code block renderer
  renderer.code = (code, language) => {
    const validLanguage = language || 'plaintext'
    const escapedCode = code
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;')

    return `<div class="code-block-wrapper">
      <div class="code-block-header">
        <span class="code-language">${validLanguage}</span>
        <button class="copy-code-btn" onclick="copyCodeToClipboard(this)" title="Copy code">
          <i class="fas fa-copy"></i>
        </button>
      </div>
      <pre class="code-block"><code class="language-${validLanguage}">${escapedCode}</code></pre>
    </div>`
  }

  // Enhanced inline code renderer
  renderer.codespan = (code) => {
    return `<code class="inline-code">${code}</code>`
  }

  // Enhanced blockquote renderer
  renderer.blockquote = (quote) => {
    const lowerQuote = quote.toLowerCase()
    let className = 'blockquote'
    let icon = '💬'

    if (lowerQuote.includes('note:') || lowerQuote.includes('📝')) {
      className += ' note'
      icon = '📝'
    } else if (lowerQuote.includes('warning:') || lowerQuote.includes('⚠️')) {
      className += ' warning'
      icon = '⚠️'
    } else if (lowerQuote.includes('tip:') || lowerQuote.includes('💡')) {
      className += ' tip'
      icon = '💡'
    } else if (lowerQuote.includes('important:') || lowerQuote.includes('❗')) {
      className += ' important'
      icon = '❗'
    }

    return `<blockquote class="${className}">
      <div class="blockquote-icon">${icon}</div>
      <div class="blockquote-content">${quote}</div>
    </blockquote>`
  }

  // Enhanced table renderer
  renderer.table = (header, body) => {
    return `<div class="table-wrapper">
      <table class="medical-table">
        <thead>${header}</thead>
        <tbody>${body}</tbody>
      </table>
    </div>`
  }

  // Enhanced link renderer
  renderer.link = (href, title, text) => {
    const isExternal = href?.startsWith('http://') || href?.startsWith('https://')
    const targetAttrs = isExternal ? ' target="_blank" rel="noopener noreferrer"' : ''
    const titleAttr = title ? ` title="${title}"` : ''
    const icon = isExternal ? ' <i class="fas fa-external-link-alt"></i>' : ''
    return `<a href="${href}"${targetAttrs}${titleAttr}>${text}${icon}</a>`
  }

  return renderer
}

// Configure marked.js
marked.setOptions({
  gfm: true,
  breaks: false,
  renderer: createRenderer(),
})

// Helper function to copy code to clipboard (needs to be on window for onclick)
if (typeof window !== 'undefined') {
  ;(window as Window & { copyCodeToClipboard?: (button: HTMLElement) => void })
    .copyCodeToClipboard = (button: HTMLElement) => {
    const codeBlock = button
      .closest('.code-block-wrapper')
      ?.querySelector('code')
    if (!codeBlock) return

    const code = codeBlock.textContent || ''
    navigator.clipboard.writeText(code).then(() => {
      const originalHTML = button.innerHTML
      button.innerHTML = '<i class="fas fa-check"></i>'
      button.classList.add('copied')

      setTimeout(() => {
        button.innerHTML = originalHTML
        button.classList.remove('copied')
      }, 2000)
    })
  }
}

export function sanitizeHtml(html: string): string {
  return DOMPurify.sanitize(html, {
    ALLOWED_TAGS: [
      'h1',
      'h2',
      'h3',
      'h4',
      'h5',
      'h6',
      'p',
      'br',
      'hr',
      'strong',
      'em',
      'u',
      's',
      'sub',
      'sup',
      'ul',
      'ol',
      'li',
      'blockquote',
      'code',
      'pre',
      'a',
      'table',
      'thead',
      'tbody',
      'tr',
      'th',
      'td',
      'div',
      'span',
      'i',
      'button',
    ],
    ALLOWED_ATTR: [
      'class',
      'id',
      'style',
      'href',
      'title',
      'target',
      'rel',
      'start',
      'onclick',
    ],
    ALLOWED_URI_REGEXP:
      /^(?:(?:(?:f|ht)tps?|mailto|tel|callto|sms|cid|xmpp):|[^a-z]|[a-z+.]+(?:[^a-z+.:-]|$))/i,
  })
}

function renderClinicalJson(payload: unknown): string | null {
  if (typeof payload !== 'object' || payload === null) return null

  const data = payload as Record<string, unknown>
  const sections: string[] = []

  if (typeof data.clinical_overview === 'string') {
    sections.push(
      `<section class="diagnosis-section"><h3>🏥 Clinical Overview</h3><p>${data.clinical_overview}</p></section>`,
    )
  }

  if (Array.isArray(data.differential_diagnoses)) {
    const list = data.differential_diagnoses
      .map((item) => {
        if (typeof item !== 'object' || item === null) return null
        const entry = item as Record<string, unknown>
        const title = entry.diagnosis ?? 'Diagnosis'
        const probability =
          typeof entry.probability_percent === 'number'
            ? `<span class="probability-badge">${entry.probability_percent}%</span>`
            : ''
        const evidence = entry.evidence
          ? `<p class="diagnosis-evidence">${entry.evidence}</p>`
          : ''
        return `<li><div class="diagnosis-title">${title}</div>${probability}${evidence}</li>`
      })
      .filter(Boolean)
      .join('')

    if (list) {
      sections.push(
        `<section class="diagnosis-section"><h3>🔍 Differential Diagnoses</h3><ul>${list}</ul></section>`,
      )
    }
  }

  if (Array.isArray(data.immediate_workup)) {
    const list = data.immediate_workup.map((item) => `<li>${item}</li>`).join('')
    sections.push(
      `<section class="diagnosis-section"><h3>🔬 Immediate Workup</h3><ul>${list}</ul></section>`,
    )
  }

  if (Array.isArray(data.management)) {
    const list = data.management.map((item) => `<li>${item}</li>`).join('')
    sections.push(
      `<section class="diagnosis-section"><h3>💊 Management</h3><ul>${list}</ul></section>`,
    )
  }

  if (typeof data.additional_information_needed === 'string') {
    sections.push(
      `<section class="diagnosis-section"><h3>ℹ️ Additional Information</h3><p>${data.additional_information_needed}</p></section>`,
    )
  }

  if (Array.isArray(data.sources_used) && data.sources_used.length > 0) {
    sections.push(
      `<section class="diagnosis-section"><h3>📚 Sources</h3><p>${data.sources_used.join(', ')}</p></section>`,
    )
  }

  if (!sections.length) {
    return null
  }

  return `<article class="diagnosis-card">${sections.join('')}</article>`
}

// ===== ENHANCED MARKDOWN RENDERER =====
function renderMarkdownWithEnhancements(markdown: string): string {
  // Decode HTML entities first
  const decodedMarkdown = decodeHTMLEntities(markdown)

  // Fix markdown spacing (add blank lines between elements)
  let fixedMarkdown = fixMarkdownSpacing(decodedMarkdown)

  // Fix emoji on separate line from heading text
  fixedMarkdown = fixedMarkdown.replace(
    /(##\s*[\u{1F300}-\u{1F9FF}\u{2600}-\u{26FF}])\s*\n\s*([A-Z])/gu,
    '$1 $2',
  )

  // Convert **BOLD HEADINGS** to proper markdown headings
  sectionHeadings.forEach((heading) => {
    const escapedHeading = heading.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    const pattern = new RegExp(`\\*\\*${escapedHeading}\\*\\*`, 'gi')
    const titleCase = heading.toLowerCase().replace(/\b\w/g, (l) => l.toUpperCase())
    fixedMarkdown = fixedMarkdown.replace(pattern, `\n\n## ${titleCase}\n\n`)
  })

  // Clean up multiple consecutive blank lines
  fixedMarkdown = fixedMarkdown.replace(/\n{3,}/g, '\n\n')

  // Remove blank lines at the very start
  fixedMarkdown = fixedMarkdown.replace(/^\n+/, '')

  // Pre-process fixed markdown for medical-specific enhancements
  let processedMarkdown = fixedMarkdown

  // Highlight percentages (e.g., "85%")
  processedMarkdown = processedMarkdown.replace(
    /(\d+(?:\.\d+)?%)/g,
    '<span class="probability-badge">$1</span>',
  )

  // Highlight medical ranges (e.g., "120/80 mmHg")
  processedMarkdown = processedMarkdown.replace(
    /(\d+\/\d+\s*(?:mmHg|mg\/dL|g\/dL|mEq\/L))/g,
    '<span class="medical-value">$1</span>',
  )

  // Highlight temperature (e.g., "38.5°C" or "101.3°F")
  processedMarkdown = processedMarkdown.replace(
    /(\d+(?:\.\d+)?°[CF])/g,
    '<span class="medical-value">$1</span>',
  )

  // Parse markdown to HTML
  const html = marked.parse(processedMarkdown) as string

  return html
}

export function renderModelResponse(content: string): string {
  if (!content) return ''

  const trimmed = content.trim()

  // Check if it's a JSON response
  if (trimmed.startsWith('{') && trimmed.endsWith('}')) {
    try {
      const json = JSON.parse(trimmed)
      const rendered = renderClinicalJson(json)
      if (rendered) {
        return sanitizeHtml(rendered)
      }
    } catch {
      // fall back to markdown renderer
    }
  }

  // Check if it's a differential diagnosis response with **DIFFERENTIAL DIAGNOSIS**
  if (trimmed.includes('**DIFFERENTIAL DIAGNOSIS**')) {
    // Use enhanced markdown renderer
    const html = renderMarkdownWithEnhancements(trimmed)
    return sanitizeHtml(html)
  }

  // Use enhanced markdown renderer
  const html = renderMarkdownWithEnhancements(trimmed)
  return sanitizeHtml(html)
}
