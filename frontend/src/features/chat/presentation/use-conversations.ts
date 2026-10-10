import { useCallback, useEffect, useRef, useState } from 'react'

import { describeError } from '@/shared/http/describe-error'

import type { ConversationRef, ConversationSummary } from '../domain/chat'
import { useQuestionGateway } from './question-gateway-context'

export interface ConversationsState {
  /** `null` enquanto a primeira carga não terminou. */
  readonly conversations: readonly ConversationSummary[] | null
  readonly error: string | null
  /** Uma resposta foi guardada: a conversa sobe para o topo do histórico. */
  touch: (conversation: ConversationRef, isNew: boolean) => void
  /** Lança o erro para quem chamou mostrar na hora (ex.: título recusado). */
  rename: (id: string, title: string) => Promise<void>
  remove: (id: string) => Promise<void>
}

export function useConversations(): ConversationsState {
  const gateway = useQuestionGateway()
  const [conversations, setConversations] = useState<ConversationSummary[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const mounted = useRef(true)

  // Carga inicial: o estado só muda nos callbacks da promessa, nunca no corpo do efeito.
  useEffect(() => {
    mounted.current = true
    const controller = new AbortController()
    gateway.listConversations(controller.signal).then(
      (list) => {
        if (mounted.current) setConversations(list)
      },
      (caught: unknown) => {
        if (mounted.current && !controller.signal.aborted) setError(describeError(caught))
      },
    )
    return () => {
      mounted.current = false
      controller.abort()
    }
  }, [gateway])

  const touch = useCallback((conversation: ConversationRef, isNew: boolean) => {
    const now = new Date()
    setConversations((current) => {
      const list = current ?? []
      const existing = list.find((c) => c.id === conversation.id)
      const updated: ConversationSummary = existing
        ? {
            ...existing,
            title: conversation.title,
            updatedAt: now,
            exchangeCount: existing.exchangeCount + 1,
          }
        : { ...conversation, createdAt: now, updatedAt: now, exchangeCount: 1 }
      return [updated, ...list.filter((c) => c.id !== conversation.id)]
    })
    if (isNew) setError(null)
  }, [])

  const rename = useCallback(
    async (id: string, title: string) => {
      const renamed = await gateway.renameConversation(id, title.trim())
      setConversations(
        (current) =>
          current?.map((c) => (c.id === id ? { ...c, title: renamed.title } : c)) ?? current,
      )
    },
    [gateway],
  )

  const remove = useCallback(
    async (id: string) => {
      await gateway.deleteConversation(id)
      setConversations((current) => current?.filter((c) => c.id !== id) ?? current)
    },
    [gateway],
  )

  return { conversations, error, touch, rename, remove }
}
