import { z } from 'zod'

import { InvalidResponseError } from '@/shared/http/errors'
import type { HttpClient } from '@/shared/http/http-client'

import type { ManualsGateway, ManualSummary } from '../domain/manuals'

const UPLOAD_TIMEOUT_MS = 120_000

const manualSchema = z.object({
  id: z.string(),
  title: z.string(),
  file_name: z.string(),
  status: z.enum(['pending', 'processing', 'indexed', 'failed']),
  page_count: z.number().int().nullable(),
  chunk_count: z.number().int().nullable(),
  failure_reason: z.string().nullable(),
  created_at: z.iso.datetime({ offset: true }),
})

function toManual(body: unknown): ManualSummary {
  const result = manualSchema.safeParse(body)
  if (!result.success) throw new InvalidResponseError({ cause: result.error })
  const m = result.data
  return {
    id: m.id,
    title: m.title,
    fileName: m.file_name,
    status: m.status,
    pageCount: m.page_count,
    chunkCount: m.chunk_count,
    failureReason: m.failure_reason,
    createdAt: new Date(m.created_at),
  }
}

export class HttpManualsGateway implements ManualsGateway {
  readonly #http: HttpClient

  constructor(http: HttpClient) {
    this.#http = http
  }

  async list(): Promise<ManualSummary[]> {
    const body = await this.#http.getJson('/api/v1/manuals')
    if (!Array.isArray(body)) throw new InvalidResponseError()
    return body.map(toManual)
  }

  async upload(file: File): Promise<ManualSummary> {
    const form = new FormData()
    form.append('file', file, file.name)
    return toManual(
      await this.#http.postForm('/api/v1/manuals', form, { timeoutMs: UPLOAD_TIMEOUT_MS }),
    )
  }

  async reindex(id: string): Promise<ManualSummary> {
    return toManual(await this.#http.postJson(`/api/v1/manuals/${encodeURIComponent(id)}/reindex`))
  }

  async remove(id: string): Promise<void> {
    await this.#http.delete(`/api/v1/manuals/${encodeURIComponent(id)}`)
  }

  fileUrl(id: string): string {
    return this.#http.url(`/api/v1/manuals/${encodeURIComponent(id)}/file`)
  }
}
