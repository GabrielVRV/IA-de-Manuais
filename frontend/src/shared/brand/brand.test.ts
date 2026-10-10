import { describe, expect, it, vi } from 'vitest'

import { applyBrand, BrandError, DEFAULT_BRAND, loadBrand, parseBrand } from './brand'

describe('parseBrand', () => {
  it('fills what is missing with the neutral brand', () => {
    expect(parseBrand({ name: 'ACME IA', colors: { accent: '#ff8800' } })).toEqual({
      ...DEFAULT_BRAND,
      name: 'ACME IA',
      colors: { primary: DEFAULT_BRAND.colors.primary, accent: '#ff8800' },
    })
  })

  it.each([
    ['empty name', { name: '  ' }],
    ['color without #', { colors: { primary: '0046b4' } }],
    ['no examples', { examples: [] }],
    ['not an object', 'ACME'],
  ])('rejects %s', (_case, raw) => {
    expect(() => parseBrand(raw)).toThrow(BrandError)
  })
})

describe('loadBrand', () => {
  it('reads the file bypassing the browser cache', async () => {
    const fetchFn = vi.fn<typeof fetch>().mockResolvedValue(Response.json({ name: 'ACME IA' }))

    const brand = await loadBrand('./brand/brand.json', fetchFn)

    expect(brand.name).toBe('ACME IA')
    expect(fetchFn).toHaveBeenCalledWith('./brand/brand.json', { cache: 'no-store' })
  })

  it('falls back to the neutral brand when there is no file', async () => {
    const fetchFn = vi.fn<typeof fetch>().mockResolvedValue(new Response(null, { status: 404 }))

    await expect(loadBrand('./brand/brand.json', fetchFn)).resolves.toBe(DEFAULT_BRAND)
  })

  it('falls back to the neutral brand when the file is invalid', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => undefined)
    const fetchFn = vi.fn<typeof fetch>().mockResolvedValue(Response.json({ name: 42 }))

    await expect(loadBrand('./brand/brand.json', fetchFn)).resolves.toBe(DEFAULT_BRAND)
    expect(warn).toHaveBeenCalled()
    warn.mockRestore()
  })
})

describe('applyBrand', () => {
  it('exposes the colors as CSS variables and names the tab', () => {
    const root = document.createElement('div')

    applyBrand({ ...DEFAULT_BRAND, name: 'ACME IA' }, root)

    expect(root.style.getPropertyValue('--brand-primary')).toBe(DEFAULT_BRAND.colors.primary)
    expect(root.style.getPropertyValue('--brand-accent')).toBe(DEFAULT_BRAND.colors.accent)
    expect(document.title).toBe('ACME IA')
  })
})
