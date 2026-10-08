import { createContext, use } from 'react'

import type { QuestionGateway } from '../domain/chat'

/** Injeção de dependência: a implementação concreta é fornecida em main.tsx. */
export const QuestionGatewayContext = createContext<QuestionGateway | null>(null)

export function useQuestionGateway(): QuestionGateway {
  const gateway = use(QuestionGatewayContext)
  if (!gateway) {
    throw new Error('useQuestionGateway precisa estar dentro de <QuestionGatewayContext>')
  }
  return gateway
}
