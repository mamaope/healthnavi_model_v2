/**
 * Lazy loader for markdown rendering. Avoids pulling marked + DOMPurify into the
 * initial bundle; the markdown chunk loads only when the first assistant message
 * is rendered.
 */
let renderFn: ((content: string) => string) | null = null

function escapeHtml(text: string): string {
  if (typeof document === 'undefined') {
    return text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
  }
  const div = document.createElement('div')
  div.textContent = text
  return div.innerHTML
}

const fallbackRenderer = (content: string): string => {
  const str = typeof content === 'string' ? content : (content != null ? String(content) : '')
  if (!str.trim()) return ''
  return escapeHtml(str).replace(/\n/g, '<br />')
}

export function getRenderModelResponse(): (content: string) => string {
  return renderFn ?? fallbackRenderer
}

export function loadMarkdownRenderer(): Promise<(content: string) => string> {
  if (renderFn) return Promise.resolve(renderFn)
  return import('./markdown').then((m) => {
    renderFn = m.renderModelResponse
    return renderFn
  })
}
