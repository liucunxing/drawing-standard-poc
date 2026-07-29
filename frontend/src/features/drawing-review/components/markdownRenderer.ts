import DOMPurify from 'dompurify'
import MarkdownIt from 'markdown-it'

const markdown = new MarkdownIt({ html: true, linkify: true, typographer: false })

const sanitizeConfig = {
  ALLOWED_TAGS: [
    'a', 'blockquote', 'br', 'code', 'del', 'div', 'em', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'hr', 'li', 'mark', 'ol', 'p', 'pre', 'span', 'strong', 'table', 'tbody', 'td', 'th', 'thead', 'tr', 'ul',
  ],
  ALLOWED_ATTR: ['href', 'title', 'rel', 'colspan', 'rowspan'],
  ALLOW_DATA_ATTR: false,
}

export function renderSafeMarkdown(value: string | null | undefined): string {
  return String(DOMPurify.sanitize(markdown.render(value || ''), sanitizeConfig))
}
