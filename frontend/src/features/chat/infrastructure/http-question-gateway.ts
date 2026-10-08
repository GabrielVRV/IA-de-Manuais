import { z } from 'zod'

import { InvalidResponseError } from '@/shared/http/errors'
import type { HttpClient } from '@/shared/http/http-client'

import type { Answer, Citation, QuestionGateway } from '../domain/chat'

// Generoso de propósito: com o provedor de IA sobrecarregado, a API repete a chamada
// algumas vezes antes de desistir.
export const QUESTION_TIMEOUT_MS = 150_000

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

export class HttpQuestionGateway implements QuestionGateway {
  readonly #http: HttpClient

  constructor(http: HttpClient) {
    this.#http = http
  }

  async ask(question: string, signal?: AbortSignal): Promise<Answer> {
    const body = await this.#http.postJson(
      '/api/v1/questions',
      { question },
      { signal, timeoutMs: QUESTION_TIMEOUT_MS },
    )
    const result = answerSchema.safeParse(body)
    if (!result.success) throw new InvalidResponseError({ cause: result.error })

    const { answer, found, citations } = result.data
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

  sourceUrl(citation: Citation): string {
    const url = this.#http.url(`/api/v1/manuals/${encodeURIComponent(citation.manualId)}/file`)
    const [firstPage] = citation.pages
    // #page=N é entendido pelo leitor de PDF embutido dos navegadores.
    return firstPage === undefined ? url : `${url}#page=${String(firstPage)}`
  }
}
