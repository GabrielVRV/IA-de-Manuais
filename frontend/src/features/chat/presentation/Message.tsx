import { useEffect, useState } from 'react'
import Markdown from 'react-markdown'

import { copyText } from '@/shared/copy-text'
import { cx } from '@/shared/cx'
import { VisorBot } from '@/shared/mascot/VisorBot'

import type { Answer, ChatMessage } from '../domain/chat'
import styles from './Chat.module.css'
import { useQuestionGateway } from './question-gateway-context'
import { STOPPED_MESSAGE } from './use-chat'

interface MessageProps {
  readonly message: ChatMessage
  readonly onRetry: (id: number) => void
  readonly retryDisabled: boolean
}

const STILL = { x: 0, y: 0.2 }

export function Message({ message, onRetry, retryDisabled }: MessageProps) {
  switch (message.role) {
    case 'user':
      return (
        <div className={styles.userRow}>
          <p className={styles.userBubble}>{message.text}</p>
        </div>
      )
    case 'assistant':
      return <AssistantMessage answer={message.answer} fresh={message.fresh} />
    case 'error': {
      const stopped = message.text === STOPPED_MESSAGE
      return (
        <div className={styles.assistantRow}>
          <Avatar mood={stopped ? 'watching' : 'error'} />
          <div
            className={styles.errorCard}
            data-tone={stopped ? 'neutral' : 'danger'}
            role={stopped ? 'status' : 'alert'}
          >
            <p>{message.text}</p>
            <button
              type="button"
              className={styles.ghostButton}
              onClick={() => {
                onRetry(message.id)
              }}
              disabled={retryDisabled}
            >
              <Icon d="M2.5 8a5.5 5.5 0 1 0 1.7-4M2.5 2.5v3h3" />
              Tentar novamente
            </button>
          </div>
        </div>
      )
    }
  }
}

function AssistantMessage({ answer, fresh }: { readonly answer: Answer; readonly fresh: boolean }) {
  const gateway = useQuestionGateway()

  return (
    <div className={styles.assistantRow}>
      <Avatar mood={answer.found ? 'happy' : 'watching'} />
      <article className={styles.answer} data-found={answer.found} data-fresh={fresh}>
        {!answer.found && (
          <span className={styles.notFoundTag}>
            <Icon d="M8 5v3.5M8 11h.01M8 1.5a6.5 6.5 0 1 0 0 13 6.5 6.5 0 0 0 0-13z" />
            Não consta nos manuais
          </span>
        )}
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
                    <span className={styles.sourceIcon} aria-hidden="true">
                      <Icon d="M4 1.5h5.5L13 5v9.5H4zM9.5 1.5V5H13M6.5 8.5h4M6.5 11h4" />
                    </span>
                    <span className={styles.sourceTitle}>{citation.manualTitle}</span>
                    <span className={styles.sourcePages}>{citation.pagesLabel}</span>
                  </a>
                </li>
              ))}
            </ul>
          </footer>
        )}
        <div className={styles.answerActions}>
          <CopyButton text={answer.text} />
        </div>
      </article>
    </div>
  )
}

function CopyButton({ text }: { readonly text: string }) {
  const [state, setState] = useState<'idle' | 'copied' | 'failed'>('idle')

  useEffect(() => {
    if (state === 'idle') return
    const timer = setTimeout(() => {
      setState('idle')
    }, 2000)
    return () => {
      clearTimeout(timer)
    }
  }, [state])

  return (
    <button
      type="button"
      className={cx(styles.ghostButton, state === 'copied' && styles.copied)}
      onClick={() => {
        void copyText(text).then((ok) => {
          setState(ok ? 'copied' : 'failed')
        })
      }}
    >
      {state === 'copied' ? (
        <Icon d="M3 8.5l3 3 7-7" />
      ) : (
        <Icon d="M5.5 5.5V2.5h8v8h-3M2.5 5.5h8v8h-8z" />
      )}
      <span aria-live="polite">
        {state === 'copied'
          ? 'Copiado!'
          : state === 'failed'
            ? 'Não foi possível copiar'
            : 'Copiar'}
      </span>
    </button>
  )
}

const THINKING_STEPS = [
  'Consultando os manuais…',
  'Procurando os trechos mais relevantes…',
  'Lendo as páginas encontradas…',
  'Escrevendo a resposta…',
]
const THINKING_STEP_MS = 2600

/** Enquanto a resposta não chega: o robô "pensa" e conta em que etapa está. */
export function Thinking() {
  const [step, setStep] = useState(0)

  useEffect(() => {
    const timer = setInterval(() => {
      setStep((current) => Math.min(current + 1, THINKING_STEPS.length - 1))
    }, THINKING_STEP_MS)
    return () => {
      clearInterval(timer)
    }
  }, [])

  return (
    <div className={styles.assistantRow}>
      <Avatar mood="thinking" animated />
      <div className={styles.thinking}>
        <span key={step} className={styles.thinkingText}>
          {THINKING_STEPS[step]}
        </span>
        <span className={styles.thinkingBar} aria-hidden="true" />
      </div>
    </div>
  )
}

function Avatar({
  mood,
  animated = false,
}: {
  readonly mood: 'watching' | 'happy' | 'thinking' | 'error'
  readonly animated?: boolean
}) {
  return (
    <span className={cx(styles.avatar, !animated && styles.avatarStill)} aria-hidden="true">
      <VisorBot mood={mood} gaze={STILL} />
    </span>
  )
}

export function Icon({ d }: { readonly d: string }) {
  return (
    <svg className={styles.icon} viewBox="0 0 16 16" aria-hidden="true">
      <path d={d} />
    </svg>
  )
}
