import { describe, expect, it, vi } from 'vitest'

import { InvalidResponseError } from '@/shared/http/errors'
import { HttpClient } from '@/shared/http/http-client'

import { HttpUsageGateway } from './http-usage-gateway'

const totals = {
  questions: 2,
  input_tokens: 900,
  output_tokens: 100,
  total_tokens: 1000,
  cost_usd: 0.0004,
  cost_is_partial: false,
}

const apiReport = {
  first_day: '2026-11-04',
  last_day: '2026-11-05',
  timezone: 'America/Sao_Paulo',
  totals,
  by_day: [
    { day: '2026-11-04', totals: { ...totals, questions: 0 } },
    { day: '2026-11-05', totals },
  ],
  by_user: [{ user_id: 'u1', username: 'maria', display_name: 'Maria', totals }],
  by_model: [{ model: 'gpt-4.1-mini', priced: true, totals }],
  unpriced_models: [],
}

function client(body: unknown) {
  const fetchFn = vi
    .fn<typeof fetch>()
    .mockImplementation(() => Promise.resolve(Response.json(body)))
  return { http: new HttpClient('http://api', { fetchFn }), fetchFn }
}

describe('HttpUsageGateway', () => {
  it('asks for the period and maps the report', async () => {
    const { http, fetchFn } = client(apiReport)

    const report = await new HttpUsageGateway(http).report(7)

    expect(fetchFn).toHaveBeenCalledWith('http://api/api/v1/usage?days=7', expect.anything())
    expect(report.byUser).toEqual([
      {
        userId: 'u1',
        username: 'maria',
        displayName: 'Maria',
        totals: {
          questions: 2,
          inputTokens: 900,
          outputTokens: 100,
          totalTokens: 1000,
          costUsd: 0.0004,
          costIsPartial: false,
        },
      },
    ])
    expect(report.byDay.map((d) => d.day)).toEqual(['2026-11-04', '2026-11-05'])
    expect(report.byModel[0]?.model).toBe('gpt-4.1-mini')
  })

  it('rejects an unexpected response', async () => {
    const { http } = client({ totals: 'x' })

    await expect(new HttpUsageGateway(http).report(30)).rejects.toBeInstanceOf(InvalidResponseError)
  })
})
