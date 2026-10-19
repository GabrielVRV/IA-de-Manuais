import { z } from 'zod'

import { InvalidResponseError } from '@/shared/http/errors'
import type { HttpClient } from '@/shared/http/http-client'

import type {
  ManualsGateway,
  ManualSummary,
  SyncCheck,
  SyncRun,
  SyncStatus,
} from '../domain/manuals'

const UPLOAD_TIMEOUT_MS = 120_000
// Ler a pasta de rede (e a planilha) pode demorar bem mais que uma requisição comum.
const SYNC_TIMEOUT_MS = 120_000

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

const syncActionSchema = z.enum(['add', 'update', 'retitle', 'remove', 'unchanged', 'ignore'])

const syncCheckSchema = z.object({
  counts: z.record(syncActionSchema, z.number().int()),
  to_index: z.number().int(),
  items: z.array(
    z.object({
      action: syncActionSchema,
      file_name: z.string(),
      title: z.string(),
      reason: z.string().nullable(),
    }),
  ),
})

const syncRunSchema = z.object({
  started_at: z.iso.datetime({ offset: true }),
  started_by: z.string(),
  finished_at: z.iso.datetime({ offset: true }).nullable(),
  running: z.boolean(),
  total: z.number().int(),
  done: z.number().int(),
  succeeded: z.number().int(),
  failures: z.array(
    z.object({ action: syncActionSchema, file_name: z.string(), detail: z.string() }),
  ),
  error: z.string().nullable(),
})

const syncStatusSchema = z.object({
  enabled: z.boolean(),
  running: z.boolean(),
  last_run: syncRunSchema.nullable(),
})

function parse<T extends z.ZodType>(schema: T, body: unknown): z.infer<T> {
  const result = schema.safeParse(body)
  if (!result.success) throw new InvalidResponseError({ cause: result.error })
  return result.data
}

function toSyncRun(run: z.infer<typeof syncRunSchema>): SyncRun {
  return {
    startedAt: new Date(run.started_at),
    startedBy: run.started_by,
    finishedAt: run.finished_at ? new Date(run.finished_at) : null,
    running: run.running,
    total: run.total,
    done: run.done,
    succeeded: run.succeeded,
    failures: run.failures.map((f) => ({
      action: f.action,
      fileName: f.file_name,
      detail: f.detail,
    })),
    error: run.error,
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

  async syncStatus(): Promise<SyncStatus> {
    const status = parse(syncStatusSchema, await this.#http.getJson('/api/v1/sync'))
    return {
      enabled: status.enabled,
      running: status.running,
      lastRun: status.last_run ? toSyncRun(status.last_run) : null,
    }
  }

  async checkSync(): Promise<SyncCheck> {
    const check = parse(
      syncCheckSchema,
      await this.#http.postJson('/api/v1/sync/check', undefined, { timeoutMs: SYNC_TIMEOUT_MS }),
    )
    return {
      counts: check.counts,
      toIndex: check.to_index,
      items: check.items.map((item) => ({
        action: item.action,
        fileName: item.file_name,
        title: item.title,
        reason: item.reason,
      })),
    }
  }

  async startSync(): Promise<SyncRun> {
    const body = await this.#http.postJson('/api/v1/sync/run', undefined, {
      timeoutMs: SYNC_TIMEOUT_MS,
    })
    return toSyncRun(parse(syncRunSchema, body))
  }
}
