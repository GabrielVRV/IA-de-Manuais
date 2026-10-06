import { describe, expect, it } from 'vitest'

import { HttpError, InvalidResponseError, NetworkError } from '@/shared/http/errors'
import type { HttpClient } from '@/shared/http/http-client'

import { HttpHealthGateway } from './http-health-gateway'

const clientReturning = (result: () => Promise<unknown>) =>
  ({ getJson: result }) as unknown as HttpClient

const report = { status: 'up', version: '0.1.0', components: { database: 'up' } }

describe('HttpHealthGateway', () => {
  it('maps a healthy response', async () => {
    const gateway = new HttpHealthGateway(clientReturning(() => Promise.resolve(report)))

    await expect(gateway.check()).resolves.toEqual(report)
  })

  it('reads the health report sent along with a 503', async () => {
    const degraded = { ...report, status: 'down', components: { database: 'down' } }
    const gateway = new HttpHealthGateway(
      clientReturning(() => Promise.reject(new HttpError(503, degraded))),
    )

    await expect(gateway.check()).resolves.toEqual(degraded)
  })

  it('rejects responses outside the contract', async () => {
    const gateway = new HttpHealthGateway(clientReturning(() => Promise.resolve({ status: 'ok' })))

    await expect(gateway.check()).rejects.toBeInstanceOf(InvalidResponseError)
  })

  it('propagates other failures', async () => {
    const gateway = new HttpHealthGateway(clientReturning(() => Promise.reject(new NetworkError())))

    await expect(gateway.check()).rejects.toBeInstanceOf(NetworkError)
  })
})
