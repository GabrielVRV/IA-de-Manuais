import { type KeyboardEvent, useState } from 'react'

import { isValidQuestion, QUESTION_MAX_LENGTH } from '../domain/chat'
import styles from './Chat.module.css'

const COUNTER_THRESHOLD = QUESTION_MAX_LENGTH - 200

interface ComposerProps {
  readonly disabled: boolean
  readonly onSubmit: (question: string) => void
}

export function Composer({ disabled, onSubmit }: ComposerProps) {
  const [text, setText] = useState('')
  const canSend = !disabled && isValidQuestion(text)

  const submit = () => {
    if (!canSend) return
    onSubmit(text)
    setText('')
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
      className={styles.composer}
      onSubmit={(event) => {
        event.preventDefault()
        submit()
      }}
    >
      <label htmlFor="question" className={styles.visuallyHidden}>
        Sua pergunta sobre os manuais
      </label>
      <textarea
        id="question"
        className={styles.input}
        value={text}
        onChange={(event) => {
          setText(event.target.value)
        }}
        onKeyDown={handleKeyDown}
        placeholder="Pergunte sobre um equipamento… (Enter envia, Shift+Enter quebra linha)"
        maxLength={QUESTION_MAX_LENGTH}
        rows={2}
      />
      <div className={styles.composerActions}>
        {text.length > COUNTER_THRESHOLD && (
          <span className={styles.counter}>
            {text.length}/{QUESTION_MAX_LENGTH}
          </span>
        )}
        <button type="submit" className={styles.sendButton} disabled={!canSend}>
          Perguntar
        </button>
      </div>
    </form>
  )
}
