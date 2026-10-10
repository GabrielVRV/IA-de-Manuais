import { type KeyboardEvent, type RefObject, useState } from 'react'

import { cx } from '@/shared/cx'

import { isValidQuestion, QUESTION_MAX_LENGTH } from '../domain/chat'
import styles from './Chat.module.css'
import { Icon } from './Message'

const COUNTER_THRESHOLD = QUESTION_MAX_LENGTH - 200

/** O que o campo está fazendo agora: o robô da tela inicial acompanha. */
export interface ComposerActivity {
  readonly focused: boolean
  readonly length: number
}

interface ComposerProps {
  readonly pending: boolean
  /** Sem conversa carregada (ex.: abrindo do histórico): não dá para perguntar ainda. */
  readonly disabled: boolean
  readonly onSubmit: (question: string) => void
  readonly onStop: () => void
  readonly onActivity?: (activity: ComposerActivity) => void
  readonly inputRef?: RefObject<HTMLTextAreaElement | null>
}

export function Composer({
  pending,
  disabled,
  onSubmit,
  onStop,
  onActivity,
  inputRef,
}: ComposerProps) {
  const [text, setText] = useState('')
  const [focused, setFocused] = useState(false)
  const canSend = !pending && !disabled && isValidQuestion(text)

  const report = (next: ComposerActivity) => {
    onActivity?.(next)
  }

  const submit = () => {
    if (!canSend) return
    onSubmit(text)
    setText('')
    report({ focused, length: 0 })
  }

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    // Enter envia; Shift+Enter quebra linha. isComposing evita enviar no meio de um acento.
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault()
      submit()
    }
  }

  return (
    <form
      className={cx(styles.composer, focused && styles.composerFocused)}
      onSubmit={(event) => {
        event.preventDefault()
        submit()
      }}
    >
      <label htmlFor="question" className={styles.visuallyHidden}>
        Sua pergunta sobre os manuais
      </label>
      <textarea
        ref={inputRef}
        id="question"
        className={styles.input}
        value={text}
        onChange={(event) => {
          setText(event.target.value)
          report({ focused: true, length: event.target.value.length })
        }}
        onFocus={() => {
          setFocused(true)
          report({ focused: true, length: text.length })
        }}
        onBlur={() => {
          setFocused(false)
          report({ focused: false, length: text.length })
        }}
        onKeyDown={handleKeyDown}
        placeholder="Pergunte sobre um equipamento, peça ou procedimento…"
        maxLength={QUESTION_MAX_LENGTH}
        rows={1}
      />
      <div className={styles.composerBar}>
        <span className={styles.keyHint}>
          <kbd>Enter</kbd> envia · <kbd>Shift</kbd>+<kbd>Enter</kbd> quebra linha
        </span>
        {text.length > COUNTER_THRESHOLD && (
          <span className={styles.counter}>
            {text.length}/{QUESTION_MAX_LENGTH}
          </span>
        )}
        {pending ? (
          <button
            type="button"
            className={cx(styles.sendButton, styles.stopButton)}
            onClick={onStop}
            aria-label="Parar resposta"
            title="Parar resposta"
          >
            <svg viewBox="0 0 16 16" aria-hidden="true">
              <rect x="4" y="4" width="8" height="8" rx="1.5" />
            </svg>
          </button>
        ) : (
          <button
            type="submit"
            className={styles.sendButton}
            disabled={!canSend}
            aria-label="Perguntar"
            title="Perguntar (Enter)"
          >
            <Icon d="M8 13V3M3.5 7.5 8 3l4.5 4.5" />
          </button>
        )}
      </div>
    </form>
  )
}
