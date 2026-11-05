import { createContext, use } from 'react'

import type { AssistantsGateway } from '../domain/assistants'

/** Injeção de dependência: a implementação concreta é fornecida em main.tsx. */
export const AssistantsGatewayContext = createContext<AssistantsGateway | null>(null)

export function useAssistantsGateway(): AssistantsGateway {
  const gateway = use(AssistantsGatewayContext)
  if (!gateway) {
    throw new Error('useAssistantsGateway precisa estar dentro de <AssistantsGatewayContext>')
  }
  return gateway
}
