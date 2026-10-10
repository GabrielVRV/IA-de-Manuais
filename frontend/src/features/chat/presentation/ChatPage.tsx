import { useCallback, useState } from 'react'
import { useMatch, useNavigate } from 'react-router'

import type { ConversationRef } from '../domain/chat'
import { Chat } from './Chat'
import styles from './ChatPage.module.css'
import { HistorySidebar } from './HistorySidebar'
import { useChat } from './use-chat'
import { useConversations } from './use-conversations'

/** Rota de uma conversa do histórico; `/` é uma conversa nova. */
export const CONVERSATION_PATH = '/c/:conversationId'

/**
 * Tela do chat: histórico à esquerda e a conversa aberta à direita.
 * Fica numa rota pai única, para não ser recriada ao trocar de conversa.
 */
export function ChatPage({ userName }: { readonly userName: string }) {
  const conversationId = useMatch(CONVERSATION_PATH)?.params.conversationId ?? null
  const navigate = useNavigate()
  const history = useConversations()
  const [historyOpen, setHistoryOpen] = useState(false)
  const { touch } = history

  const onSaved = useCallback(
    (conversation: ConversationRef, isNew: boolean) => {
      touch(conversation, isNew)
      // replace: o "voltar" do navegador não cai numa conversa nova vazia.
      if (isNew) void navigate(`/c/${encodeURIComponent(conversation.id)}`, { replace: true })
    },
    [touch, navigate],
  )

  const chat = useChat({ conversationId, onSaved })
  const title = history.conversations?.find((c) => c.id === conversationId)?.title ?? null

  return (
    <div className={styles.page}>
      <HistorySidebar
        history={history}
        activeId={conversationId}
        open={historyOpen}
        onClose={() => {
          setHistoryOpen(false)
        }}
        onActiveDeleted={() => {
          void navigate('/', { replace: true })
        }}
      />
      <Chat
        chat={chat}
        title={conversationId ? title : null}
        userName={firstName(userName)}
        conversationKey={conversationId ?? 'nova'}
        onOpenHistory={() => {
          setHistoryOpen(true)
        }}
      />
    </div>
  )
}

/** "GABRIEL VIARO" (como vem do TOTVS) vira "Gabriel" na saudação. */
function firstName(name: string): string {
  const first = name.trim().split(/\s+/)[0] ?? ''
  if (first !== first.toUpperCase()) return first
  return first.charAt(0) + first.slice(1).toLowerCase()
}
