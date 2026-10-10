// Mesmos limites da API (domain/question.py e domain/conversation.py no backend).
export const QUESTION_MIN_LENGTH = 3
export const QUESTION_MAX_LENGTH = 2000
export const TITLE_MAX_LENGTH = 80

export interface Citation {
  readonly manualId: string
  readonly manualTitle: string
  readonly pages: readonly number[]
  readonly pagesLabel: string
}

export interface Answer {
  readonly text: string
  /** false quando a informação não consta nos manuais. */
  readonly found: boolean
  readonly citations: readonly Citation[]
}

/** O suficiente para identificar uma conversa e mostrá-la no histórico. */
export interface ConversationRef {
  readonly id: string
  readonly title: string
}

export interface ConversationSummary extends ConversationRef {
  readonly createdAt: Date
  readonly updatedAt: Date
  readonly exchangeCount: number
}

export interface Exchange {
  readonly question: string
  readonly answer: Answer
  readonly askedAt: Date
}

export interface Conversation extends ConversationRef {
  readonly createdAt: Date
  readonly updatedAt: Date
  readonly exchanges: readonly Exchange[]
}

/** Resposta de uma pergunta e a conversa onde ela foi guardada. */
export interface ChatReply {
  readonly answer: Answer
  readonly conversation: ConversationRef
}

export type ChatMessage =
  | { readonly id: number; readonly role: 'user'; readonly text: string }
  | {
      readonly id: number
      readonly role: 'assistant'
      readonly answer: Answer
      /** Acabou de chegar (anima a entrada); falso para as carregadas do histórico. */
      readonly fresh: boolean
    }
  | {
      readonly id: number
      readonly role: 'error'
      readonly text: string
      /** Pergunta que falhou, para tentar de novo. */
      readonly question: string
    }

export function isValidQuestion(text: string): boolean {
  const length = text.trim().length
  return length >= QUESTION_MIN_LENGTH && length <= QUESTION_MAX_LENGTH
}

export function isValidTitle(text: string): boolean {
  const length = text.trim().length
  return length > 0 && length <= TITLE_MAX_LENGTH
}

export interface HistoryGroup {
  readonly label: string
  readonly conversations: readonly ConversationSummary[]
}

const DAY_MS = 24 * 60 * 60 * 1000

/**
 * Agrupa o histórico por quando cada conversa foi usada pela última vez
 * (Hoje, Ontem, 7 dias, 30 dias, mais antigas), mantendo a ordem recebida.
 */
export function groupByRecency(
  conversations: readonly ConversationSummary[],
  now: Date,
): HistoryGroup[] {
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()
  const buckets: [label: string, since: number][] = [
    ['Hoje', startOfToday],
    ['Ontem', startOfToday - DAY_MS],
    ['Últimos 7 dias', startOfToday - 7 * DAY_MS],
    ['Últimos 30 dias', startOfToday - 30 * DAY_MS],
    ['Mais antigas', -Infinity],
  ]
  const groups = new Map<string, ConversationSummary[]>()
  for (const conversation of conversations) {
    const time = conversation.updatedAt.getTime()
    const [label] = buckets.find(([, since]) => time >= since) ?? ['Mais antigas']
    const group = groups.get(label) ?? []
    group.push(conversation)
    groups.set(label, group)
  }
  return buckets
    .map(([label]) => ({ label, conversations: groups.get(label) ?? [] }))
    .filter((group) => group.conversations.length > 0)
}

/**
 * Porta: perguntas, histórico e fontes, independente de transporte.
 *
 * Toda conversa pertence ao usuário logado: o servidor só devolve as dele.
 */
export interface QuestionGateway {
  /** Sem `conversationId`, começa uma conversa nova. */
  ask(question: string, conversationId: string | null, signal?: AbortSignal): Promise<ChatReply>
  listConversations(signal?: AbortSignal): Promise<ConversationSummary[]>
  getConversation(id: string, signal?: AbortSignal): Promise<Conversation>
  renameConversation(id: string, title: string): Promise<ConversationRef>
  deleteConversation(id: string): Promise<void>
  /** Link que abre o PDF do manual na primeira página citada. */
  sourceUrl(citation: Citation): string
}
