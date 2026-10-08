// Mesmos limites da API (domain/question.py no backend).
export const QUESTION_MIN_LENGTH = 3
export const QUESTION_MAX_LENGTH = 2000

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

export type ChatMessage =
  | { readonly id: number; readonly role: 'user'; readonly text: string }
  | { readonly id: number; readonly role: 'assistant'; readonly answer: Answer }
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

/** Porta: como a interface faz perguntas e chega às fontes, independente de transporte. */
export interface QuestionGateway {
  ask(question: string, signal?: AbortSignal): Promise<Answer>
  /** Link que abre o PDF do manual na primeira página citada. */
  sourceUrl(citation: Citation): string
}
