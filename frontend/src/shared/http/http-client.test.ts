import { describe, expect, it, vi } from 'vitest'

import { HttpError, NetworkError, TimeoutError } from './errors'
import { HttpClient } from './http-client'

const jsonResponse = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })

/** fetch falso que só termina quando o sinal é abortado. */
const hangingFetch: typeof fetch = (_input, init) =>
  new Promise((_resolve, reject) => {
    init?.signal?.addEventListener('abort', () => {
      reject(new DOMException('aborted', 'AbortError'))
    })
  })

describe('HttpClient', () => {
  it('joins base URL and path, and returns the parsed JSON', async () => {
    const fetchFn = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse({ ok: true }))
    const client = new HttpClient('http://api.local/', { fetchFn })

    const body = await client.getJson('/api/v1/health')

    expect(body).toEqual({ ok: true })
    expect(fetchFn).toHaveBeenCalledWith('http://api.local/api/v1/health', expect.anything())
  })

  it('throws HttpError carrying status and body on error responses', async () => {
    const fetchFn = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse({ status: 'down' }, 503))
    const client = new HttpClient('http://api.local', { fetchFn })

    const error: unknown = await client.getJson('/x').catch((e: unknown) => e)

    expect(error).toBeInstanceOf(HttpError)
    expect(error).toMatchObject({ status: 503, body: { status: 'down' } })
  })

  it('throws NetworkError when the server is unreachable', async () => {
    const fetchFn = vi.fn<typeof fetch>().mockRejectedValue(new TypeError('Failed to fetch'))
    const client = new HttpClient('http://api.local', { fetchFn })

    await expect(client.getJson('/x')).rejects.toBeInstanceOf(NetworkError)
  })

  it('throws TimeoutError when the server takes too long', async () => {
    const client = new HttpClient('http://api.local', { fetchFn: hangingFetch, timeoutMs: 10 })

    await expect(client.getJson('/x')).rejects.toBeInstanceOf(TimeoutError)
  })

  it('sends JSON bodies with POST', async () => {
    const fetchFn = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse({ ok: true }))
    const client = new HttpClient('http://api.local', { fetchFn })

    await client.postJson('/api/v1/questions', { question: 'Pressão?' })

    const [url, init] = fetchFn.mock.calls[0] ?? []
    expect(url).toBe('http://api.local/api/v1/questions')
    expect(init).toMatchObject({
      method: 'POST',
      body: JSON.stringify({ question: 'Pressão?' }),
      headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
    })
  })

  it('accepts a per-request timeout', async () => {
    const client = new HttpClient('http://api.local', { fetchFn: hangingFetch, timeoutMs: 60_000 })

    await expect(client.getJson('/x', { timeoutMs: 10 })).rejects.toBeInstanceOf(TimeoutError)
  })

  it('builds absolute URLs for links', () => {
    expect(new HttpClient('http://api.local/').url('/api/v1/manuals/1/file')).toBe(
      'http://api.local/api/v1/manuals/1/file',
    )
  })

  it('propagates caller cancellation without wrapping it', async () => {
    const client = new HttpClient('http://api.local', { fetchFn: hangingFetch })
    const controller = new AbortController()

    const request = client.getJson('/x', { signal: controller.signal })
    controller.abort()

    await expect(request).rejects.toHaveProperty('name', 'AbortError')
  })
})
