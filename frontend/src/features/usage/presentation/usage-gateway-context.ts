import { createContext, use } from 'react'

import type { UsageGateway } from '../domain/usage'

/** Injeção de dependência: a implementação concreta é fornecida em main.tsx. */
export const UsageGatewayContext = createContext<UsageGateway | null>(null)

export function useUsageGateway(): UsageGateway {
  const gateway = use(UsageGatewayContext)
  if (!gateway) throw new Error('useUsageGateway precisa estar dentro de <UsageGatewayContext>')
  return gateway
}
