import { z } from 'zod'

import { InvalidResponseError } from '@/shared/http/errors'
import type { HttpClient } from '@/shared/http/http-client'

import type {
  Answer,
  ChatReply,
  Citation,
  Conversation,
  ConversationRef,
  ConversationSummary,
  QuestionGateway,
} from '../domain/chat'

// Generoso de propósito: com o provedor de IA sobrecarregado, a API repete a chamada
// algumas vezes antes de desistir.
export const QUESTION_TIMEOUT_MS = 150_000

const datetime = z.iso.datetime({ offset: true })

const citationSchema = z.object({
  manual_id: z.string(),
  manual_title: z.string(),
  pages: z.array(z.number().int().positive()),
  pages_label: z.string(),
})

const answerSchema = z.object({
  answer: z.string(),
  found: z.boolean(),
  citations: z.array(citationSchema),
})

const conversationRefSchema = z.object({ id: z.string(), title: z.string() })

const chatReplySchema = answerSchema.extend({ conversation: conversationRefSchema })

const summarySchema = conversationRefSchema.extend({
  created_at: datetime,
  updated_at: datetime,
  exchange_count: z.number().int().nonnegative(),
})

const conversationSchema = conversationRefSchema.extend({
  created_at: datetime,
  updated_at: datetime,
  exchanges: z.array(z.object({ question: z.string(), answer: answerSchema, asked_at: datetime })),
})

function parse<T>(schema: z.ZodType<T>, body: unknown): T {
  const result = schema.safeParse(body)
  if (!result.success) throw new InvalidResponseError({ cause: result.error })
  return result.data
}

function toAnswer({ answer, found, citations }: z.infer<typeof answerSchema>): Answer {
  return {
    text: answer,
    found,
    citations: citations.map((c): Citation => ({
      manualId: c.manual_id,
      manualTitle: c.manual_title,
      pages: c.pages,
      pagesLabel: c.pages_label,
    })),
  }
}

const conversationPath = (id: string) => `/api/v1/conversations/${encodeURIComponent(id)}`

export class HttpQuestionGateway implements QuestionGateway {
  readonly #http: HttpClient

  constructor(http: HttpClient) {
    this.#http = http
  }

  async ask(
    question: string,
    conversationId: string | null,
    signal?: AbortSignal,
  ): Promise<ChatReply> {
    const body = await this.#http.postJson(
      '/api/v1/questions',
      conversationId ? { question, conversation_id: conversationId } : { question },
      { signal, timeoutMs: QUESTION_TIMEOUT_MS },
    )
    const reply = parse(chatReplySchema, body)
    return { answer: toAnswer(reply), conversation: reply.conversation }
  }

  async listConversations(signal?: AbortSignal): Promise<ConversationSummary[]> {
    const body = await this.#http.getJson('/api/v1/conversations', { signal })
    return parse(z.array(summarySchema), body).map((c) => ({
      id: c.id,
      title: c.title,
      createdAt: new Date(c.created_at),
      updatedAt: new Date(c.updated_at),
      exchangeCount: c.exchange_count,
    }))
  }

  async getConversation(id: string, signal?: AbortSignal): Promise<Conversation> {
    const c = parse(conversationSchema, await this.#http.getJson(conversationPath(id), { signal }))
    return {
      id: c.id,
      title: c.title,
      createdAt: new Date(c.created_at),
      updatedAt: new Date(c.updated_at),
      exchanges: c.exchanges.map((e) => ({
        question: e.question,
        answer: toAnswer(e.answer),
        askedAt: new Date(e.asked_at),
      })),
    }
  }

  async renameConversation(id: string, title: string): Promise<ConversationRef> {
    return parse(conversationRefSchema, await this.#http.patchJson(conversationPath(id), { title }))
  }

  async deleteConversation(id: string): Promise<void> {
    await this.#http.delete(conversationPath(id))
  }

  sourceUrl(citation: Citation): string {
    const url = this.#http.url(`/api/v1/manuals/${encodeURIComponent(citation.manualId)}/file`)
    const [firstPage] = citation.pages
    // #page=N é entendido pelo leitor de PDF embutido dos navegadores.
    return firstPage === undefined ? url : `${url}#page=${String(firstPage)}`
  }
}
