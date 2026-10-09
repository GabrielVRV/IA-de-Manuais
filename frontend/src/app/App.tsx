import { Navigate, NavLink, Route, Routes } from 'react-router'

import { isAdmin, managesPasswordHere } from '@/features/auth/domain/auth'
import { AuthGate } from '@/features/auth/presentation/AuthGate'
import { ChangePasswordForm } from '@/features/auth/presentation/ChangePasswordForm'
import { useCurrentUser, useSession } from '@/features/auth/presentation/session-context'
import { Chat } from '@/features/chat/presentation/Chat'
import { ApiStatus } from '@/features/health/presentation/ApiStatus'
import { ManualsAdmin } from '@/features/manuals/presentation/ManualsAdmin'
import { UsersAdmin } from '@/features/users/presentation/UsersAdmin'
import { cx } from '@/shared/cx'
import ui from '@/styles/ui.module.css'

import styles from './App.module.css'
import { Layout } from './Layout'

export function App() {
  return (
    <AuthGate>
      <AuthenticatedApp />
    </AuthGate>
  )
}

function AuthenticatedApp() {
  const user = useCurrentUser()
  const admin = isAdmin(user)

  return (
    <Layout nav={<MainNav admin={admin} />} actions={<HeaderActions />}>
      <Routes>
        <Route path="/" element={<Chat />} />
        {managesPasswordHere(user) && <Route path="/senha" element={<PasswordPage />} />}
        {/* Usuários comuns que tentarem abrir uma tela de administração voltam ao chat. */}
        <Route path="/manuais" element={admin ? <ManualsAdmin /> : <Navigate to="/" replace />} />
        <Route path="/usuarios" element={admin ? <UsersAdmin /> : <Navigate to="/" replace />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Layout>
  )
}

function MainNav({ admin }: { readonly admin: boolean }) {
  const link = ({ isActive }: { isActive: boolean }) =>
    cx(styles.navLink, isActive && styles.active)
  return (
    <nav className={styles.nav} aria-label="Navegação principal">
      <NavLink to="/" end className={link}>
        Chat
      </NavLink>
      {admin && (
        <>
          <NavLink to="/manuais" className={link}>
            Manuais
          </NavLink>
          <NavLink to="/usuarios" className={link}>
            Usuários
          </NavLink>
        </>
      )}
    </nav>
  )
}

function HeaderActions() {
  const user = useCurrentUser()
  const { logout } = useSession()
  return (
    <div className={styles.actions}>
      <ApiStatus />
      {managesPasswordHere(user) ? (
        <NavLink to="/senha" className={styles.userName} title="Trocar minha senha">
          {user.displayName}
        </NavLink>
      ) : (
        <span className={styles.userName} title="Usuário do TOTVS">
          {user.displayName}
        </span>
      )}
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
  )
}

function PasswordPage() {
  return (
    <div className={ui.page}>
      <div className={cx(ui.card, styles.narrow)}>
        <h2 className={ui.pageTitle}>Trocar minha senha</h2>
        <ChangePasswordForm />
      </div>
    </div>
  )
}
