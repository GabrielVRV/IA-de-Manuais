import { useEffect, useState } from 'react'

import type { AssistantId, AvailableAssistant } from '@/features/assistants/domain/assistants'
import { useAssistantsGateway } from '@/features/assistants/presentation/assistants-gateway-context'

/**
 * O assistente e se o usuário pode usá-lo; null enquanto carrega ou se a consulta falhar.
 * Na falha, o chat continua aberto: a API recusa a pergunta e o chat mostra a mensagem.
 */
export function useAssistantAccess(id: AssistantId): AvailableAssistant | null {
  const gateway = useAssistantsGateway()
  const [assistant, setAssistant] = useState<AvailableAssistant | null>(null)

  useEffect(() => {
    let active = true
    gateway.mine().then(
      (list) => {
        if (active) setAssistant(new Map(list.map((a) => [a.id, a])).get(id) ?? null)
      },
      () => {
        if (active) setAssistant(null)
      },
    )
    return () => {
      active = false
    }
  }, [gateway, id])

  return assistant
}
