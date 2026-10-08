import { useCallback, useEffect, useRef, useState } from 'react'

import { describeError } from '@/shared/http/describe-error'

import { type ChatMessage, isValidQuestion } from '../domain/chat'
import { useQuestionGateway } from './question-gateway-context'

export interface ChatState {
  readonly messages: readonly ChatMessage[]
  readonly pending: boolean
  ask: (question: string) => void
  retry: (errorMessageId: number) => void
  reset: () => void
}

export function useChat(): ChatState {
  const gateway = useQuestionGateway()
  const [messages, setMessages] = useState<readonly ChatMessage[]>([])
  const [pending, setPending] = useState(false)
  // Contador em vez de crypto.randomUUID(): ele não existe em páginas servidas por HTTP.
  const nextId = useRef(0)
  const inFlight = useRef<AbortController | null>(null)

  const newId = () => ++nextId.current

  const send = useCallback(
    async (question: string) => {
      const controller = new AbortController()
      inFlight.current = controller
      setPending(true)
      try {
        const answer = await gateway.ask(question, controller.signal)
        if (controller.signal.aborted) return
        setMessages((current) => [...current, { id: newId(), role: 'assistant', answer }])
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
      if (inFlight.current || !isValidQuestion(question)) return
      setMessages((current) => [...current, { id: newId(), role: 'user', text: question }])
      void send(question)
    },
    [send],
  )

  const retry = useCallback(
    (errorMessageId: number) => {
      if (inFlight.current) return
      const failed = messages.find((m) => m.id === errorMessageId)
      if (failed?.role !== 'error') return
      // A pergunta original continua na conversa; só o aviso de erro sai.
      setMessages((current) => current.filter((m) => m.id !== errorMessageId))
      void send(failed.question)
    },
    [messages, send],
  )

  const reset = useCallback(() => {
    inFlight.current?.abort()
    inFlight.current = null
    setPending(false)
    setMessages([])
  }, [])

  useEffect(() => () => inFlight.current?.abort(), [])

  return { messages, pending, ask, retry, reset }
}
