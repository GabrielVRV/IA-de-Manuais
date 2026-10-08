import { useEffect, useRef } from 'react'

import styles from './Chat.module.css'
import { Composer } from './Composer'
import { Message } from './Message'
import { useChat } from './use-chat'

const SUGGESTIONS = [
  'Qual a pressão máxima de trabalho do equipamento?',
  'Como fazer a troca de óleo, passo a passo?',
  'O que significa o código de alarme exibido no painel?',
]

export function Chat() {
  const { messages, pending, ask, retry, reset } = useChat()
  const endRef = useRef<HTMLDivElement>(null)

  // Mantém a mensagem mais recente visível.
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages, pending])

  const isEmpty = messages.length === 0 && !pending

  return (
    <section className={styles.chat} aria-label="Conversa com o assistente">
      <div className={styles.messages} role="log" aria-live="polite" aria-busy={pending}>
        {isEmpty ? (
          <div className={styles.empty}>
            <h2 className={styles.emptyTitle}>Tire suas dúvidas sobre os manuais</h2>
            <p className={styles.emptyText}>
              As respostas vêm dos manuais cadastrados, com o manual e a página de cada informação.
            </p>
            <ul className={styles.suggestions}>
              {SUGGESTIONS.map((suggestion) => (
                <li key={suggestion}>
                  <button
                    type="button"
                    className={styles.suggestion}
                    onClick={() => {
                      ask(suggestion)
                    }}
                  >
                    {suggestion}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ) : (
          messages.map((message) => (
            <Message key={message.id} message={message} onRetry={retry} retryDisabled={pending} />
          ))
        )}
        {pending && (
          <div className={styles.typing}>
            <span className={styles.dots} aria-hidden="true">
              <span />
              <span />
              <span />
            </span>
            Consultando os manuais…
          </div>
        )}
        <div ref={endRef} />
      </div>

      <div className={styles.footer}>
        {!isEmpty && (
          <button type="button" className={styles.textButton} onClick={reset}>
            Nova conversa
          </button>
        )}
        <Composer disabled={pending} onSubmit={ask} />
        <p className={styles.disclaimer}>
          O assistente pode errar. Confira informações críticas de segurança no manual original.
        </p>
      </div>
    </section>
  )
}
