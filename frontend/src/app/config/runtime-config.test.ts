import { describe, expect, it, vi } from 'vitest'

import { loadRuntimeConfig, parseRuntimeConfig, RuntimeConfigError } from './runtime-config'

describe('parseRuntimeConfig', () => {
  it('accepts a valid URL and strips trailing slashes', () => {
    expect(parseRuntimeConfig({ apiBaseUrl: 'http://servidor:8000/' })).toEqual({
      apiBaseUrl: 'http://servidor:8000',
    })
  })

  it.each([
    ['missing field', {}],
    ['not a URL', { apiBaseUrl: 'servidor:8000' }],
    ['unsupported protocol', { apiBaseUrl: 'ftp://servidor' }],
    ['not an object', 'http://servidor'],
  ])('rejects %s', (_case, raw) => {
    expect(() => parseRuntimeConfig(raw)).toThrow(RuntimeConfigError)
  })
})

describe('loadRuntimeConfig', () => {
  it('fetches the file bypassing the browser cache', async () => {
    const fetchFn = vi
      .fn<typeof fetch>()
      .mockResolvedValue(Response.json({ apiBaseUrl: 'http://servidor:8000' }))

    const config = await loadRuntimeConfig('./config.json', fetchFn)

    expect(config.apiBaseUrl).toBe('http://servidor:8000')
    expect(fetchFn).toHaveBeenCalledWith('./config.json', { cache: 'no-store' })
  })

  it('fails clearly when the file is missing', async () => {
    const fetchFn = vi.fn<typeof fetch>().mockResolvedValue(new Response(null, { status: 404 }))

    await expect(loadRuntimeConfig('./config.json', fetchFn)).rejects.toThrow('HTTP 404')
  })

  it('fails clearly when the file is not JSON', async () => {
    const fetchFn = vi.fn<typeof fetch>().mockResolvedValue(new Response('<html>'))

    await expect(loadRuntimeConfig('./config.json', fetchFn)).rejects.toThrow('JSON válido')
  })
})
