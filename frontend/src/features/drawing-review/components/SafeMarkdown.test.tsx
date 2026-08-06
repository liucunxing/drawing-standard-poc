import { describe, expect, it } from 'vitest'
import { renderSafeMarkdown } from './markdownRenderer'

describe('SafeMarkdown', () => {
  it('removes XSS payloads and inline event or style attributes', () => {
    const html = renderSafeMarkdown('<script>alert(1)</script><img src=x onerror="alert(2)" style="color:red"><a href="javascript:alert(3)">bad</a>')
    expect(html).not.toMatch(/script|onerror|style=|javascript:/i)
  })

  it('keeps allowed mark and table markup visible after sanitization', () => {
    const html = renderSafeMarkdown('<mark>重点</mark>\n\n| 标准号 | 结果 |\n| --- | --- |\n| GB 1 | 完全符合 |')
    expect(html).toContain('<mark>重点</mark>')
    expect(html).toContain('<table>')
  })

  it('renders the real rowspan and colspan table shape instead of dropping its content', () => {
    const html = renderSafeMarkdown('<table><tr><td rowspan=1 colspan=15>管 口 表</td></tr><tr><td rowspan=1 colspan=2>符号</td><td>N1</td></tr></table>')
    const container = document.createElement('div')
    container.innerHTML = html

    expect(container.querySelectorAll('table')).toHaveLength(1)
    expect(container.querySelectorAll('tr')).toHaveLength(2)
    expect(container.querySelectorAll('td')).toHaveLength(3)
    expect(container.querySelector('td')).toHaveAttribute('colspan', '15')
    expect(container).toHaveTextContent('管 口 表')
  })
})
