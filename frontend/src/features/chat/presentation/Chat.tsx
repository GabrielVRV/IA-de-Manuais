import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router'

import { useBrand } from '@/shared/brand/brand-context'
import { cx } from '@/shared/cx'
import { type Gaze, VisorBot } from '@/shared/mascot/VisorBot'
import ui from '@/styles/ui.module.css'

import styles from './Chat.module.css'
import { Composer, type ComposerActivity } from './Composer'
import { Icon, Message, Thinking } from './Message'
import type { ChatState } from './use-chat'

const SUGGESTION_ICONS = [
  'M8 1.5v2M8 12.5v2M1.5 8h2M12.5 8h2M8 5a3 3 0 1 0 0 6 3 3 0 0 0 0-6z',
  'M3 13.5 9.5 7M11 2.5l2.5 2.5-4 4L7 6.5zM2.5 14l1-3 2 2z',
  'M2.5 3.5h11M2.5 8h11M2.5 12.5h7',
  'M9 1.5 3.5 9H8l-1 5.5L12.5 7H8z',
]

interface ChatProps {
  readonly chat: ChatState
  /** Título da conversa aberta; `null` numa conversa nova. */
  readonly title: string | null
  /** Primeiro nome de quem está usando, para a saudação. */
  readonly userName: string
  readonly onOpenHistory: () => void
  /** Muda a cada conversa aberta: o campo de pergunta volta a ter o foco. */
  readonly conversationKey: string
}

export function Chat({ chat, title, userName, onOpenHistory, conversationKey }: ChatProps) {
  const { messages, pending, loading, loadError, ask, retry, stop } = chat
  const brand = useBrand()
  const scrollRef = useRef<HTMLDivElement>(null)
  const endRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const [activity, setActivity] = useState<ComposerActivity>({ focused: false, length: 0 })
  const [awayFromEnd, setAwayFromEnd] = useState(false)

  // Mantém a mensagem mais recente visível.
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages, pending])

  // Com mouse (computador), o campo de pergunta já fica pronto para digitar.
  useEffect(() => {
    if (typeof window.matchMedia === 'function' && window.matchMedia('(pointer: fine)').matches) {
      inputRef.current?.focus()
    }
  }, [conversationKey])

  const isEmpty = messages.length === 0 && !pending && !loading && !loadError

  // O robô da tela inicial olha para o campo enquanto a pessoa digita.
  const gaze: Gaze | undefined = activity.focused
    ? { x: -0.7 + (Math.min(activity.length, 50) / 50) * 1.4, y: 1 }
    : undefined

  return (
    <section className={styles.chat} aria-label="Conversa com o assistente">
      <header className={styles.topBar}>
        <button
          type="button"
          className={cx(styles.iconButton, styles.historyToggle)}
          onClick={onOpenHistory}
          aria-label="Abrir o histórico de conversas"
        >
          <Icon d="M2.5 4h11M2.5 8h11M2.5 12h11" />
        </button>
        <h2 className={styles.conversationTitle}>{title ?? 'Nova conversa'}</h2>
        {!isEmpty && (
          <Link to="/" className={styles.newChatLink}>
            <Icon d="M8 3v10M3 8h10" />
            Nova conversa
          </Link>
        )}
      </header>

      <div
        ref={scrollRef}
        className={styles.messages}
        role="log"
        aria-live="polite"
        aria-busy={pending || loading}
        onScroll={(event) => {
          const el = event.currentTarget
          setAwayFromEnd(el.scrollHeight - el.scrollTop - el.clientHeight > 240)
        }}
      >
        <div className={styles.thread}>
          {isEmpty && (
            <div className={styles.welcome}>
              <VisorBot mood="watching" gaze={gaze} className={styles.welcomeBot} />
              <h2 className={styles.welcomeTitle}>
                Olá, {userName}! <span>Como posso ajudar?</span>
              </h2>
              <p className={styles.welcomeText}>
                Pergunte em linguagem natural. Eu procuro nos manuais e mostro de qual manual e
                página veio cada informação.
              </p>
              <ul className={styles.suggestions}>
                {brand.examples.slice(0, 4).map((suggestion, index) => (
                  <li key={suggestion} style={{ animationDelay: `${String(120 + index * 70)}ms` }}>
                    <button
                      type="button"
                      className={styles.suggestion}
                      onClick={() => {
                        ask(suggestion)
                      }}
                    >
                      <span className={styles.suggestionIcon} aria-hidden="true">
                        <Icon d={SUGGESTION_ICONS[index % SUGGESTION_ICONS.length] ?? ''} />
                      </span>
                      {suggestion}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {loading && <LoadingThread />}

          {loadError && (
            <div className={styles.loadError}>
              <p className={ui.alert} data-tone="danger" role="alert">
                {loadError}
              </p>
              <Link to="/" className={styles.newChatLink}>
                Começar uma nova conversa
              </Link>
            </div>
          )}

          {messages.map((message) => (
            <Message key={message.id} message={message} onRetry={retry} retryDisabled={pending} />
          ))}
          {pending && <Thinking />}
          <div ref={endRef} />
        </div>
      </div>

      {awayFromEnd && (
        <button
          type="button"
          className={styles.toEnd}
          onClick={() => {
            endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
          }}
          aria-label="Ir para a mensagem mais recente"
        >
          <Icon d="M8 3v10M3.5 8.5 8 13l4.5-4.5" />
        </button>
      )}

      <div className={styles.footer}>
        <Composer
          pending={pending}
          disabled={loading || loadError !== null}
          onSubmit={ask}
          onStop={stop}
          onActivity={setActivity}
          inputRef={inputRef}
        />
        <p className={styles.disclaimer}>
          O assistente pode errar. Confira informações críticas de segurança no manual original.
        </p>
      </div>
    </section>
  )
}

function LoadingThread() {
  return (
    <div className={styles.loadingThread} role="status" aria-label="Abrindo a conversa">
      <span className={styles.skeletonUser} />
      <span className={styles.skeletonAnswer} />
      <span className={styles.skeletonUser} />
      <span className={styles.skeletonAnswer} />
    </div>
  )
}
