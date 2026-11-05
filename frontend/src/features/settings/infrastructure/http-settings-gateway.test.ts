import { describe, expect, it, vi } from 'vitest'

import { InvalidResponseError } from '@/shared/http/errors'
import { HttpClient } from '@/shared/http/http-client'

import { HttpSettingsGateway } from './http-settings-gateway'

function client(body: unknown, status = 200) {
  const fetchFn = vi
    .fn<typeof fetch>()
    .mockImplementation(() =>
      Promise.resolve(status === 204 ? new Response(null, { status }) : Response.json(body)),
    )
  return { http: new HttpClient('http://api', { fetchFn }), fetchFn }
}

function sentBody(fetchFn: ReturnType<typeof client>['fetchFn']): unknown {
  const body = fetchFn.mock.calls[0]?.[1]?.body
  if (typeof body !== 'string') throw new Error('a requisição não enviou JSON')
  return JSON.parse(body)
}

describe('HttpSettingsGateway', () => {
  it('maps the settings and sends only the changed fields', async () => {
    const { http, fetchFn } = client({
      usage_retention_months: 6,
      updated_at: '2026-11-05T12:00:00Z',
      updated_by: 'Ana Admin',
    })

    const settings = await new HttpSettingsGateway(http).update({ usageRetentionMonths: 6 })

    expect(settings).toEqual({
      usageRetentionMonths: 6,
      updatedAt: new Date('2026-11-05T12:00:00Z'),
      updatedBy: 'Ana Admin',
    })
    expect(fetchFn).toHaveBeenCalledWith(
      'http://api/api/v1/settings',
      expect.objectContaining({ method: 'PATCH' }),
    )
    expect(sentBody(fetchFn)).toEqual({ usage_retention_months: 6 })
  })

  it('lists and saves model prices', async () => {
    const price = {
      model: 'gpt-4.1-mini',
      configured: true,
      input_per_million: 0.4,
      output_per_million: 1.6,
    }
    const { http, fetchFn } = client(price)
    const gateway = new HttpSettingsGateway(http)

    const saved = await gateway.setModelPrice({
      model: 'gpt-4.1-mini',
      inputPerMillion: 0.4,
      outputPerMillion: 1.6,
    })

    expect(saved).toEqual({
      model: 'gpt-4.1-mini',
      configured: true,
      inputPerMillion: 0.4,
      outputPerMillion: 1.6,
    })
    expect(fetchFn).toHaveBeenCalledWith(
      'http://api/api/v1/settings/model-prices',
      expect.objectContaining({ method: 'PUT' }),
    )
    expect(sentBody(fetchFn)).toEqual({
      model: 'gpt-4.1-mini',
      input_per_million: 0.4,
      output_per_million: 1.6,
    })
  })

  it('removes the price of a model by name, escaped in the URL', async () => {
    const { http, fetchFn } = client(null, 204)

    await new HttpSettingsGateway(http).deleteModelPrice('models/gemini 3')

    expect(fetchFn).toHaveBeenCalledWith(
      'http://api/api/v1/settings/model-prices?model=models%2Fgemini%203',
      expect.objectContaining({ method: 'DELETE' }),
    )
  })

  it('rejects an unexpected response', async () => {
    const { http } = client([{ model: 1 }])

    await expect(new HttpSettingsGateway(http).listModelPrices()).rejects.toBeInstanceOf(
      InvalidResponseError,
    )
  })
})
