import { createContext, use } from 'react'

import type { SettingsGateway } from '../domain/settings'

/** Injeção de dependência: a implementação concreta é fornecida em main.tsx. */
export const SettingsGatewayContext = createContext<SettingsGateway | null>(null)

export function useSettingsGateway(): SettingsGateway {
  const gateway = use(SettingsGatewayContext)
  if (!gateway)
    throw new Error('useSettingsGateway precisa estar dentro de <SettingsGatewayContext>')
  return gateway
}
