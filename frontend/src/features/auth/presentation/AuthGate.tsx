import { type ReactNode, useState } from 'react'

import { cx } from '@/shared/cx'
import { describeError } from '@/shared/http/describe-error'
import ui from '@/styles/ui.module.css'

import { isPending, type SessionUser } from '../domain/auth'
import styles from './Auth.module.css'
import { ChangePasswordForm } from './ChangePasswordForm'
import { LoginPage } from './LoginPage'
import { useSession } from './session-context'

/** Só deixa passar quem está logado, teve o acesso liberado e já trocou a senha provisória. */
export function AuthGate({ children }: { readonly children: ReactNode }) {
  const { state, logout } = useSession()

  if (state.status === 'loading') {
    return (
      <div className={styles.screen} role="status">
        <span className={ui.muted}>Carregando…</span>
      </div>
    )
  }
  if (state.status === 'anonymous') {
    return <LoginPage notice={state.notice} />
  }
  if (isPending(state.user)) {
    return <PendingAccess user={state.user} />
  }
  if (state.user.mustChangePassword) {
    return (
      <div className={styles.screen}>
        <div className={cx(ui.card, styles.panel)}>
          <h1 className={styles.title}>Crie sua senha</h1>
          <ChangePasswordForm intro="Você entrou com uma senha provisória. Para continuar, digite-a abaixo e escolha uma senha só sua." />
          <LogoutButton onLogout={logout} />
        </div>
      </div>
    )
  }
  return children
}

/** Primeiro acesso pelo TOTVS: o usuário já está cadastrado e aguarda um administrador. */
function PendingAccess({ user }: { readonly user: SessionUser }) {
  const { refresh, logout } = useSession()
  const [checking, setChecking] = useState(false)
  const [message, setMessage] = useState<{ tone: 'info' | 'danger'; text: string } | null>(null)

  const check = async () => {
    setChecking(true)
    setMessage(null)
    try {
      await refresh()
      // Se o acesso foi liberado, esta tela some; se não, avisamos.
      setMessage({ tone: 'info', text: 'Seu acesso ainda não foi liberado.' })
    } catch (caught) {
      setMessage({ tone: 'danger', text: describeError(caught) })
    } finally {
      setChecking(false)
    }
  }

  return (
    <div className={styles.screen}>
      <div className={cx(ui.card, styles.panel)}>
        <h1 className={styles.title}>Aguardando liberação</h1>
        <p>
          Olá, <strong>{user.displayName}</strong>. Seu acesso foi registrado e um administrador
          precisa liberá-lo antes de você usar o assistente.
        </p>
        <p className={ui.muted}>Assim que for liberado, é só entrar de novo ou verificar abaixo.</p>
        {message && (
          <p className={ui.alert} data-tone={message.tone} role="status">
            {message.text}
          </p>
        )}
        <button
          type="button"
          className={cx(ui.button, ui.primary)}
          disabled={checking}
          onClick={() => {
            void check()
          }}
        >
          {checking ? 'Verificando…' : 'Verificar novamente'}
        </button>
        <LogoutButton onLogout={logout} />
      </div>
    </div>
  )
}

function LogoutButton({ onLogout }: { readonly onLogout: () => Promise<void> }) {
  return (
    <button
      type="button"
      className={ui.button}
      onClick={() => {
        void onLogout()
      }}
    >
      Sair
    </button>
  )
}
