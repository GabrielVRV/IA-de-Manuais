import { Navigate, NavLink, Route, Routes, useLocation } from 'react-router'

import { isAdmin, managesPasswordHere } from '@/features/auth/domain/auth'
import { AuthGate } from '@/features/auth/presentation/AuthGate'
import { ChangePasswordForm } from '@/features/auth/presentation/ChangePasswordForm'
import { useCurrentUser, useSession } from '@/features/auth/presentation/session-context'
import { ChatPage } from '@/features/chat/presentation/ChatPage'
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
  const { pathname } = useLocation()
  const chat = <ChatPage userName={user.displayName} />

  return (
    <Layout
      nav={<MainNav admin={admin} />}
      actions={<HeaderActions />}
      fullWidth={isChatPath(pathname)}
    >
      <Routes>
        {/* Uma rota só para o chat: trocar de conversa não recria a tela (nem o histórico). */}
        <Route path="/" element={chat}>
          <Route path="c/:conversationId" element={null} />
        </Route>
        {managesPasswordHere(user) && <Route path="/senha" element={<PasswordPage />} />}
        {/* Usuários comuns que tentarem abrir uma tela de administração voltam ao chat. */}
        <Route path="/manuais" element={admin ? <ManualsAdmin /> : <Navigate to="/" replace />} />
        <Route path="/usuarios" element={admin ? <UsersAdmin /> : <Navigate to="/" replace />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Layout>
  )
}

/** O chat ocupa a tela inteira (histórico + conversa); as demais telas ficam centralizadas. */
function isChatPath(pathname: string): boolean {
  return pathname === '/' || pathname.startsWith('/c/')
}

function MainNav({ admin }: { readonly admin: boolean }) {
  const { pathname } = useLocation()
  const link = ({ isActive }: { isActive: boolean }) =>
    cx(styles.navLink, isActive && styles.active)
  return (
    <nav className={styles.nav} aria-label="Navegação principal">
      <NavLink to="/" className={link({ isActive: isChatPath(pathname) })}>
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
