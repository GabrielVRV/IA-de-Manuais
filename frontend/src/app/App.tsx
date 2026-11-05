import { Navigate, NavLink, Route, Routes, useLocation } from 'react-router'

import { isAdmin, managesPasswordHere } from '@/features/auth/domain/auth'
import { AccessAdmin } from '@/features/assistants/presentation/AccessAdmin'
import { AuthGate } from '@/features/auth/presentation/AuthGate'
import { ChangePasswordForm } from '@/features/auth/presentation/ChangePasswordForm'
import { useCurrentUser, useSession } from '@/features/auth/presentation/session-context'
import { ChatPage } from '@/features/chat/presentation/ChatPage'
import { ApiStatus } from '@/features/health/presentation/ApiStatus'
import { ManualsAdmin } from '@/features/manuals/presentation/ManualsAdmin'
import { SettingsAdmin } from '@/features/settings/presentation/SettingsAdmin'
import { UsageReport } from '@/features/usage/presentation/UsageReport'
import { UsersAdmin } from '@/features/users/presentation/UsersAdmin'
import { cx } from '@/shared/cx'
import { ThemeToggle } from '@/shared/theme/ThemeToggle'
import ui from '@/styles/ui.module.css'

import { AdminLayout } from './AdminLayout'
import styles from './App.module.css'
import { Layout } from './Layout'

/** Endereços de antes da área de administração, mantidos para favoritos antigos. */
const LEGACY_ADMIN_PATHS = ['manuais', 'usuarios', 'consumo', 'configuracoes'] as const

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
      fullWidth={isChatPath(pathname) || isAdminPath(pathname)}
    >
      <Routes>
        {/* Uma rota só para o chat: trocar de conversa não recria a tela (nem o histórico). */}
        <Route path="/" element={chat}>
          <Route path="c/:conversationId" element={null} />
        </Route>
        {managesPasswordHere(user) && <Route path="/senha" element={<PasswordPage />} />}
        {/* Usuários comuns que tentarem abrir a administração voltam ao chat. */}
        <Route path="/admin" element={admin ? <AdminLayout /> : <Navigate to="/" replace />}>
          <Route index element={<Navigate to="usuarios" replace />} />
          <Route path="usuarios" element={<UsersAdmin />} />
          <Route path="acessos" element={<AccessAdmin />} />
          <Route path="consumo" element={<UsageReport />} />
          <Route path="configuracoes" element={<SettingsAdmin />} />
          <Route path="manuais" element={<ManualsAdmin />} />
        </Route>
        {LEGACY_ADMIN_PATHS.map((page) => (
          <Route
            key={page}
            path={`/${page}`}
            element={<Navigate to={`/admin/${page}`} replace />}
          />
        ))}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Layout>
  )
}

/** O chat ocupa a tela inteira (histórico + conversa); as demais telas ficam centralizadas. */
function isChatPath(pathname: string): boolean {
  return pathname === '/' || pathname.startsWith('/c/')
}

/** A administração tem o próprio menu lateral e controla a própria largura. */
function isAdminPath(pathname: string): boolean {
  return pathname === '/admin' || pathname.startsWith('/admin/')
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
        <NavLink to="/admin" className={link}>
          Administração
        </NavLink>
      )}
    </nav>
  )
}

function HeaderActions() {
  const user = useCurrentUser()
  const { logout } = useSession()
  return (
    <div className={styles.actions}>
      <ThemeToggle />
      <ApiStatus />
      {managesPasswordHere(user) ? (
        <NavLink to="/senha" className={styles.userName} title="Trocar minha senha">
          {user.displayName}
        </NavLink>
      ) : (
        <span className={styles.userName} title="Usuário de rede (AD)">
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
