import { createContext, use } from 'react'

import type { ManualsGateway } from '../domain/manuals'

/** Injeção de dependência: a implementação concreta é fornecida em main.tsx. */
export const ManualsGatewayContext = createContext<ManualsGateway | null>(null)

export function useManualsGateway(): ManualsGateway {
  const gateway = use(ManualsGatewayContext)
  if (!gateway) throw new Error('useManualsGateway precisa estar dentro de <ManualsGatewayContext>')
  return gateway
}
