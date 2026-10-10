import { useCallback, useEffect, useRef, useState } from 'react'

import { describeError } from '@/shared/http/describe-error'
import { HttpError } from '@/shared/http/errors'

import {
  type ChatMessage,
  type Conversation,
  type ConversationRef,
  isValidQuestion,
} from '../domain/chat'
import { useQuestionGateway } from './question-gateway-context'

export interface ChatState {
  readonly messages: readonly ChatMessage[]
  /** Esperando a resposta de uma pergunta. */
  readonly pending: boolean
  /** Abrindo uma conversa do histórico. */
  readonly loading: boolean
  readonly loadError: string | null
  ask: (question: string) => void
  retry: (errorMessageId: number) => void
  /** Interrompe a pergunta em andamento. */
  stop: () => void
}

interface UseChatOptions {
  /** Conversa aberta (da URL); `null` é uma conversa nova, ainda vazia. */
  readonly conversationId: string | null
  /** A resposta foi guardada: `isNew` quando a pergunta começou uma conversa. */
  readonly onSaved: (conversation: ConversationRef, isNew: boolean) => void
}

export const STOPPED_MESSAGE = 'Você interrompeu a resposta.'
const NOT_FOUND_MESSAGE = 'Esta conversa não existe mais. Ela pode ter sido apagada.'

export function useChat({ conversationId, onSaved }: UseChatOptions): ChatState {
  const gateway = useQuestionGateway()
  // Conversa a que o estado abaixo pertence (a da URL, depois de cada render).
  const [shownId, setShownId] = useState(conversationId)
  // Conversa que a primeira resposta acabou de criar. Quando a URL passar para ela,
  // a tela a assume como está, sem limpar nem buscar de novo.
  const [adopting, setAdopting] = useState<string | null>(null)
  const [messages, setMessages] = useState<readonly ChatMessage[]>([])
  const [pending, setPending] = useState(false)
  const [loading, setLoading] = useState(conversationId !== null)
  const [loadError, setLoadError] = useState<string | null>(null)
  // Contador em vez de crypto.randomUUID(): ele não existe em páginas servidas por HTTP.
  const nextId = useRef(0)
  const inFlight = useRef<AbortController | null>(null)
  // O mesmo, para o efeito de carga saber que não precisa buscá-la.
  const createdId = useRef<string | null>(null)
  const onSavedRef = useRef(onSaved)
  useEffect(() => {
    onSavedRef.current = onSaved
  })

  const newId = () => ++nextId.current

  // A URL mudou. Se foi para a conversa recém-criada, só a assume; se foi para outra,
  // recomeça o estado já neste render (sem mostrar um quadro com a conversa antiga).
  if (conversationId !== shownId) {
    setShownId(conversationId)
    setAdopting(null)
    if (conversationId === null || conversationId !== adopting) {
      setMessages([])
      setPending(false)
      setLoadError(null)
      setLoading(conversationId !== null)
    }
  }
  // Entre a resposta e a URL mudar, a próxima pergunta já vai para a conversa nova.
  const activeId = shownId ?? adopting

  useEffect(() => {
    if (conversationId === null) return
    if (conversationId === createdId.current) {
      createdId.current = null
      return
    }
    const controller = new AbortController()
    gateway.getConversation(conversationId, controller.signal).then(
      (conversation) => {
        if (controller.signal.aborted) return
        setMessages(toMessages(conversation, newId))
        setLoading(false)
      },
      (error: unknown) => {
        if (controller.signal.aborted) return
        const notFound = error instanceof HttpError && error.status === 404
        setLoadError(notFound ? NOT_FOUND_MESSAGE : describeError(error))
        setLoading(false)
      },
    )
    return () => {
      controller.abort()
    }
  }, [conversationId, gateway])

  // Trocar de conversa cancela a pergunta que ainda esperava resposta.
  useEffect(
    () => () => {
      inFlight.current?.abort()
      inFlight.current = null
    },
    [conversationId],
  )

  const send = useCallback(
    async (question: string, currentId: string | null) => {
      const controller = new AbortController()
      inFlight.current = controller
      setPending(true)
      try {
        const reply = await gateway.ask(question, currentId, controller.signal)
        if (controller.signal.aborted) return
        const isNew = currentId !== reply.conversation.id
        if (isNew) {
          createdId.current = reply.conversation.id
          setAdopting(reply.conversation.id)
        }
        setMessages((current) => [
          ...current,
          { id: newId(), role: 'assistant', answer: reply.answer, fresh: true },
        ])
        onSavedRef.current(reply.conversation, isNew)
      } catch (error) {
        if (controller.signal.aborted) return
        setMessages((current) => [
          ...current,
          { id: newId(), role: 'error', text: describeError(error), question },
        ])
      } finally {
        if (inFlight.current === controller) {
          inFlight.current = null
          setPending(false)
        }
      }
    },
    [gateway],
  )

  const ask = useCallback(
    (raw: string) => {
      const question = raw.trim()
      if (inFlight.current || loading || !isValidQuestion(question)) return
      setMessages((current) => [...current, { id: newId(), role: 'user', text: question }])
      void send(question, activeId)
    },
    [send, activeId, loading],
  )

  const retry = useCallback(
    (errorMessageId: number) => {
      if (inFlight.current) return
      const failed = messages.find((m) => m.id === errorMessageId)
      if (failed?.role !== 'error') return
      // A pergunta original continua na conversa; só o aviso de erro sai.
      setMessages((current) => current.filter((m) => m.id !== errorMessageId))
      void send(failed.question, activeId)
    },
    [messages, send, activeId],
  )

  const stop = useCallback(() => {
    const controller = inFlight.current
    if (!controller) return
    controller.abort()
    inFlight.current = null
    setPending(false)
    const question = messages.findLast((m) => m.role === 'user')
    if (question?.role === 'user') {
      setMessages((current) => [
        ...current,
        { id: newId(), role: 'error', text: STOPPED_MESSAGE, question: question.text },
      ])
    }
  }, [messages])

  return { messages, pending, loading, loadError, ask, retry, stop }
}

function toMessages(conversation: Conversation, newId: () => number): ChatMessage[] {
  return conversation.exchanges.flatMap((exchange): ChatMessage[] => [
    { id: newId(), role: 'user', text: exchange.question },
    { id: newId(), role: 'assistant', answer: exchange.answer, fresh: false },
  ])
}
