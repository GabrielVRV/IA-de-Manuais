import { z } from 'zod'

import { HttpError, InvalidResponseError } from '@/shared/http/errors'
import type { HttpClient } from '@/shared/http/http-client'

import type { ApiHealth, HealthGateway } from '../domain/api-health'

const serviceStatusSchema = z.enum(['up', 'down'])

const healthResponseSchema = z.object({
  status: serviceStatusSchema,
  version: z.string(),
  components: z.record(z.string(), serviceStatusSchema),
})

export class HttpHealthGateway implements HealthGateway {
  readonly #http: HttpClient

  constructor(http: HttpClient) {
    this.#http = http
  }

  async check(signal?: AbortSignal): Promise<ApiHealth> {
    try {
      return toApiHealth(await this.#http.getJson('/api/v1/health', signal))
    } catch (error) {
      // 503 traz o relatório completo: a API está no ar, mas alguma dependência não.
      if (error instanceof HttpError && error.status === 503) return toApiHealth(error.body)
      throw error
    }
  }
}

function toApiHealth(body: unknown): ApiHealth {
  const result = healthResponseSchema.safeParse(body)
  if (!result.success) throw new InvalidResponseError({ cause: result.error })
  return result.data
}
