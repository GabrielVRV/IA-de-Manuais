import { createContext, use } from 'react'

import type { UsersGateway } from '../domain/users'

/** Injeção de dependência: a implementação concreta é fornecida em main.tsx. */
export const UsersGatewayContext = createContext<UsersGateway | null>(null)

export function useUsersGateway(): UsersGateway {
  const gateway = use(UsersGatewayContext)
  if (!gateway) throw new Error('useUsersGateway precisa estar dentro de <UsersGatewayContext>')
  return gateway
}
