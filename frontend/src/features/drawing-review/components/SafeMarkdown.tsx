import styles from './SafeMarkdown.module.css'
import { renderSafeMarkdown } from './markdownRenderer'

export function SafeMarkdown({ content }: { content: string | null | undefined }) {
  return <div className={styles.content} dangerouslySetInnerHTML={{ __html: renderSafeMarkdown(content) }} />
}
