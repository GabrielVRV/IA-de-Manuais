import { afterEach, describe, expect, it } from 'vitest'

import {
  applyThemePreference,
  readThemePreference,
  saveThemePreference,
  THEME_STORAGE_KEY,
} from './theme'

afterEach(() => {
  localStorage.clear()
  delete document.documentElement.dataset.theme
})

describe('theme preference', () => {
  it('follows the system until the user chooses', () => {
    expect(readThemePreference()).toBe('system')
  })

  it('remembers the choice and forgets it when going back to the system', () => {
    saveThemePreference('dark')
    expect(readThemePreference()).toBe('dark')

    saveThemePreference('system')
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBeNull()
  })

  it('ignores unknown saved values', () => {
    localStorage.setItem(THEME_STORAGE_KEY, 'roxo')

    expect(readThemePreference()).toBe('system')
  })

  it('survives a browser that blocks storage', () => {
    const blocked = {
      getItem: () => {
        throw new Error('bloqueado')
      },
      setItem: () => {
        throw new Error('bloqueado')
      },
      removeItem: () => {
        throw new Error('bloqueado')
      },
    } as unknown as Storage

    expect(readThemePreference(blocked)).toBe('system')
    expect(() => {
      saveThemePreference('dark', blocked)
    }).not.toThrow()
  })

  it('marks the page with the chosen theme', () => {
    const root = document.documentElement

    applyThemePreference('light')
    expect(root.dataset.theme).toBe('light')

    applyThemePreference('system')
    expect(root.dataset.theme).toBeUndefined()
  })
})
