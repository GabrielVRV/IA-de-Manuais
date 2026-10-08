import Markdown from 'react-markdown'

import type { Answer, ChatMessage } from '../domain/chat'
import styles from './Chat.module.css'
import { useQuestionGateway } from './question-gateway-context'

interface MessageProps {
  readonly message: ChatMessage
  readonly onRetry: (id: number) => void
  readonly retryDisabled: boolean
}

export function Message({ message, onRetry, retryDisabled }: MessageProps) {
  switch (message.role) {
    case 'user':
      return (
        <div className={styles.userRow}>
          <p className={styles.userBubble}>{message.text}</p>
        </div>
      )
    case 'assistant':
      return <AssistantMessage answer={message.answer} />
    case 'error':
      return (
        <div className={styles.errorBubble} role="alert">
          <p>{message.text}</p>
          <button
            type="button"
            className={styles.textButton}
            onClick={() => {
              onRetry(message.id)
            }}
            disabled={retryDisabled}
          >
            Tentar novamente
          </button>
        </div>
      )
  }
}

function AssistantMessage({ answer }: { readonly answer: Answer }) {
  const gateway = useQuestionGateway()

  return (
    <article className={styles.assistantBubble} data-found={answer.found}>
      {/* react-markdown não interpreta HTML: o texto do modelo não injeta código na página. */}
      <div className={styles.markdown}>
        <Markdown>{answer.text}</Markdown>
      </div>
      {answer.citations.length > 0 && (
        <footer className={styles.sources}>
          <span className={styles.sourcesLabel}>Fontes</span>
          <ul className={styles.sourceList}>
            {answer.citations.map((citation) => (
              <li key={citation.manualId}>
                <a
                  className={styles.sourceLink}
                  href={gateway.sourceUrl(citation)}
                  target="_blank"
                  rel="noopener noreferrer"
                  title="Abrir o manual nesta página"
                >
                  <span aria-hidden="true">📄</span> {citation.manualTitle}
                  <span className={styles.sourcePages}>{citation.pagesLabel}</span>
                </a>
              </li>
            ))}
          </ul>
        </footer>
      )}
    </article>
  )
}
