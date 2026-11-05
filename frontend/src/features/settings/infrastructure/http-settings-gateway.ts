import { z } from 'zod'

import { InvalidResponseError } from '@/shared/http/errors'
import type { HttpClient } from '@/shared/http/http-client'

import type {
  ModelPrice,
  NewModelPrice,
  SettingsChanges,
  SettingsGateway,
  SystemSettings,
} from '../domain/settings'

const settingsSchema = z.object({
  usage_retention_months: z.number(),
  updated_at: z.iso.datetime({ offset: true }).nullable(),
  updated_by: z.string().nullable(),
})

const priceSchema = z.object({
  model: z.string(),
  configured: z.boolean(),
  input_per_million: z.number().nullable(),
  output_per_million: z.number().nullable(),
})

function parse<T>(schema: z.ZodType<T>, body: unknown): T {
  const result = schema.safeParse(body)
  if (!result.success) throw new InvalidResponseError({ cause: result.error })
  return result.data
}

function toSettings(body: unknown): SystemSettings {
  const s = parse(settingsSchema, body)
  return {
    usageRetentionMonths: s.usage_retention_months,
    updatedAt: s.updated_at ? new Date(s.updated_at) : null,
    updatedBy: s.updated_by,
  }
}

function toPrice(body: unknown): ModelPrice {
  const p = parse(priceSchema, body)
  return {
    model: p.model,
    configured: p.configured,
    inputPerMillion: p.input_per_million,
    outputPerMillion: p.output_per_million,
  }
}

const PRICES = '/api/v1/settings/model-prices'

export class HttpSettingsGateway implements SettingsGateway {
  readonly #http: HttpClient

  constructor(http: HttpClient) {
    this.#http = http
  }

  async get(): Promise<SystemSettings> {
    return toSettings(await this.#http.getJson('/api/v1/settings'))
  }

  async update(changes: SettingsChanges): Promise<SystemSettings> {
    return toSettings(
      await this.#http.patchJson('/api/v1/settings', {
        usage_retention_months: changes.usageRetentionMonths,
      }),
    )
  }

  async listModelPrices(): Promise<ModelPrice[]> {
    const body = await this.#http.getJson(PRICES)
    if (!Array.isArray(body)) throw new InvalidResponseError()
    return body.map(toPrice)
  }

  async setModelPrice(price: NewModelPrice): Promise<ModelPrice> {
    return toPrice(
      await this.#http.putJson(PRICES, {
        model: price.model,
        input_per_million: price.inputPerMillion,
        output_per_million: price.outputPerMillion,
      }),
    )
  }

  async deleteModelPrice(model: string): Promise<void> {
    await this.#http.delete(`${PRICES}?model=${encodeURIComponent(model)}`)
  }
}
