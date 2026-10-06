import { createContext, use } from 'react'

import type { HealthGateway } from '../domain/api-health'

/** Injeção de dependência: a implementação concreta é fornecida em main.tsx. */
export const HealthGatewayContext = createContext<HealthGateway | null>(null)

export function useHealthGateway(): HealthGateway {
  const gateway = use(HealthGatewayContext)
  if (!gateway) throw new Error('useHealthGateway precisa estar dentro de <HealthGatewayContext>')
  return gateway
}
