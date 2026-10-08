import { createContext, use } from 'react'

import type { AuthGateway, SessionUser } from '../domain/auth'

/** Injeção de dependência: a implementação concreta é fornecida em main.tsx. */
export const AuthGatewayContext = createContext<AuthGateway | null>(null)

export function useAuthGateway(): AuthGateway {
  const gateway = use(AuthGatewayContext)
  if (!gateway) throw new Error('useAuthGateway precisa estar dentro de <AuthGatewayContext>')
  return gateway
}

export type SessionState =
  | { readonly status: 'loading' }
  | { readonly status: 'anonymous'; readonly notice?: string }
  | { readonly status: 'authenticated'; readonly user: SessionUser }

export interface Session {
  readonly state: SessionState
  login: (username: string, password: string) => Promise<void>
  logout: () => Promise<void>
  changePassword: (currentPassword: string, newPassword: string) => Promise<void>
}

export const SessionContext = createContext<Session | null>(null)

export function useSession(): Session {
  const session = use(SessionContext)
  if (!session) throw new Error('useSession precisa estar dentro de <SessionProvider>')
  return session
}

/** Usuário logado; só pode ser usado dentro da parte autenticada da aplicação. */
export function useCurrentUser(): SessionUser {
  const { state } = useSession()
  if (state.status !== 'authenticated') throw new Error('Nenhum usuário autenticado')
  return state.user
}
