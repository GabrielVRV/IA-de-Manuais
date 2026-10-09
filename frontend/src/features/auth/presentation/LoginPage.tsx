import { useState } from 'react'

import { describeError } from '@/shared/http/describe-error'
import { cx } from '@/shared/cx'
import ui from '@/styles/ui.module.css'

import styles from './Auth.module.css'
import { useSession } from './session-context'

export function LoginPage({ notice }: { readonly notice?: string | undefined }) {
  const { login } = useSession()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const submit = async () => {
    setSubmitting(true)
    setError(null)
    try {
      await login(username.trim(), password)
    } catch (caught) {
      setError(describeError(caught))
      setPassword('')
      setSubmitting(false)
    }
  }

  return (
    <div className={styles.screen}>
      <form
        className={cx(ui.card, styles.panel)}
        onSubmit={(event) => {
          event.preventDefault()
          void submit()
        }}
      >
        <h1 className={styles.title}>Assistente de Manuais</h1>
        <p className={ui.muted}>
          Entre com seu usuário e senha do TOTVS para consultar os manuais.
        </p>

        {notice && !error && (
          <p className={ui.alert} data-tone="info" role="status">
            {notice}
          </p>
        )}
        {error && (
          <p className={ui.alert} data-tone="danger" role="alert">
            {error}
          </p>
        )}

        <label className={ui.field}>
          <span className={ui.label}>Usuário</span>
          <input
            className={ui.input}
            value={username}
            onChange={(event) => {
              setUsername(event.target.value)
            }}
            autoComplete="username"
            autoCapitalize="none"
            spellCheck={false}
            required
          />
        </label>
        <label className={ui.field}>
          <span className={ui.label}>Senha</span>
          <input
            className={ui.input}
            type="password"
            value={password}
            onChange={(event) => {
              setPassword(event.target.value)
            }}
            autoComplete="current-password"
            required
          />
        </label>

        <button className={cx(ui.button, ui.primary)} type="submit" disabled={submitting}>
          {submitting ? 'Entrando…' : 'Entrar'}
        </button>
        <p className={ui.hint}>
          Esqueceu a senha? Redefina-a no TOTVS. Se o seu usuário foi criado aqui, peça a um
          administrador.
        </p>
      </form>
    </div>
  )
}
