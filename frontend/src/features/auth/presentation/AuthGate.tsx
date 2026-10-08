import type { ReactNode } from 'react'

import { cx } from '@/shared/cx'
import ui from '@/styles/ui.module.css'

import styles from './Auth.module.css'
import { ChangePasswordForm } from './ChangePasswordForm'
import { LoginPage } from './LoginPage'
import { useSession } from './session-context'

/** Só deixa passar quem está logado e já trocou a senha provisória. */
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
  if (state.user.mustChangePassword) {
    return (
      <div className={styles.screen}>
        <div className={cx(ui.card, styles.panel)}>
          <h1 className={styles.title}>Crie sua senha</h1>
          <ChangePasswordForm intro="Você entrou com uma senha provisória. Para continuar, digite-a abaixo e escolha uma senha só sua." />
          <button
            type="button"
            className={ui.button}
            onClick={() => {
              void logout()
            }}
          >
            Sair
          </button>
        </div>
      </div>
    )
  }
  return children
}
