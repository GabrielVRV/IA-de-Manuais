import { z } from 'zod'

import { InvalidResponseError } from '@/shared/http/errors'
import type { HttpClient } from '@/shared/http/http-client'

import type { UsageGateway, UsagePeriod, UsageReport, UsageTotals } from '../domain/usage'

const totalsSchema = z.object({
  questions: z.number(),
  input_tokens: z.number(),
  output_tokens: z.number(),
  total_tokens: z.number(),
  cost_usd: z.number(),
  cost_is_partial: z.boolean(),
})

const reportSchema = z.object({
  first_day: z.iso.date(),
  last_day: z.iso.date(),
  timezone: z.string(),
  totals: totalsSchema,
  by_day: z.array(z.object({ day: z.iso.date(), totals: totalsSchema })),
  by_user: z.array(
    z.object({
      user_id: z.string(),
      username: z.string(),
      display_name: z.string(),
      totals: totalsSchema,
    }),
  ),
  by_model: z.array(z.object({ model: z.string(), priced: z.boolean(), totals: totalsSchema })),
  unpriced_models: z.array(z.string()),
})

function toTotals(t: z.infer<typeof totalsSchema>): UsageTotals {
  return {
    questions: t.questions,
    inputTokens: t.input_tokens,
    outputTokens: t.output_tokens,
    totalTokens: t.total_tokens,
    costUsd: t.cost_usd,
    costIsPartial: t.cost_is_partial,
  }
}

export class HttpUsageGateway implements UsageGateway {
  readonly #http: HttpClient

  constructor(http: HttpClient) {
    this.#http = http
  }

  async report(days: UsagePeriod): Promise<UsageReport> {
    const result = reportSchema.safeParse(
      await this.#http.getJson(`/api/v1/usage?days=${String(days)}`),
    )
    if (!result.success) throw new InvalidResponseError({ cause: result.error })
    const r = result.data
    return {
      firstDay: r.first_day,
      lastDay: r.last_day,
      timezone: r.timezone,
      totals: toTotals(r.totals),
      byDay: r.by_day.map((d) => ({ day: d.day, totals: toTotals(d.totals) })),
      byUser: r.by_user.map((u) => ({
        userId: u.user_id,
        username: u.username,
        displayName: u.display_name,
        totals: toTotals(u.totals),
      })),
      byModel: r.by_model.map((m) => ({
        model: m.model,
        priced: m.priced,
        totals: toTotals(m.totals),
      })),
      unpricedModels: r.unpriced_models,
    }
  }
}
