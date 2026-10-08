import { useState } from 'react'

import { describeError } from '@/shared/http/describe-error'
import { cx } from '@/shared/cx'
import ui from '@/styles/ui.module.css'

import { PASSWORD_MAX_LENGTH, PASSWORD_MIN_LENGTH } from '../domain/auth'
import { useSession } from './session-context'

interface ChangePasswordFormProps {
  /** Texto explicando por que a troca está sendo pedida. */
  readonly intro?: string
  readonly onChanged?: () => void
}

export function ChangePasswordForm({ intro, onChanged }: ChangePasswordFormProps) {
  const { changePassword } = useSession()
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  const submit = async () => {
    setError(null)
    setDone(false)
    if (next.length < PASSWORD_MIN_LENGTH) {
      setError(`A nova senha precisa ter ao menos ${String(PASSWORD_MIN_LENGTH)} caracteres.`)
      return
    }
    if (next !== confirmation) {
      setError('A confirmação não confere com a nova senha.')
      return
    }
    setSubmitting(true)
    try {
      await changePassword(current, next)
      setCurrent('')
      setNext('')
      setConfirmation('')
      setDone(true)
      onChanged?.()
    } catch (caught) {
      setError(describeError(caught))
    } finally {
      setSubmitting(false)
    }
  }

  const passwordInput = (
    label: string,
    value: string,
    setValue: (value: string) => void,
    autoComplete: string,
  ) => (
    <label className={ui.field}>
      <span className={ui.label}>{label}</span>
      <input
        className={ui.input}
        type="password"
        value={value}
        onChange={(event) => {
          setValue(event.target.value)
        }}
        autoComplete={autoComplete}
        maxLength={PASSWORD_MAX_LENGTH}
        required
      />
    </label>
  )

  return (
    <form
      className={ui.stack}
      onSubmit={(event) => {
        event.preventDefault()
        void submit()
      }}
    >
      {intro && <p className={ui.muted}>{intro}</p>}
      {error && (
        <p className={ui.alert} data-tone="danger" role="alert">
          {error}
        </p>
      )}
      {done && (
        <p className={ui.alert} data-tone="success" role="status">
          Senha alterada com sucesso.
        </p>
      )}
      {passwordInput('Senha atual', current, setCurrent, 'current-password')}
      {passwordInput('Nova senha', next, setNext, 'new-password')}
      <span className={ui.hint}>
        Mínimo de {PASSWORD_MIN_LENGTH} caracteres. Uma frase longa é mais segura que símbolos.
      </span>
      {passwordInput('Confirme a nova senha', confirmation, setConfirmation, 'new-password')}
      <button className={cx(ui.button, ui.primary)} type="submit" disabled={submitting}>
        {submitting ? 'Salvando…' : 'Trocar senha'}
      </button>
    </form>
  )
}
