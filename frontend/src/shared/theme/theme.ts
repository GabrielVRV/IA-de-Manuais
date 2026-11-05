/**
 * Tema claro/escuro escolhido por quem usa. "system" segue o sistema operacional.
 * A escolha fica só neste navegador (localStorage) e vira `data-theme` no <html>,
 * que o global.css usa para trocar as cores.
 */
export type ThemePreference = 'system' | 'light' | 'dark'

export const THEME_PREFERENCES: readonly ThemePreference[] = ['system', 'light', 'dark']

export const THEME_STORAGE_KEY = 'ma-theme'

function isPreference(value: unknown): value is ThemePreference {
  return THEME_PREFERENCES.includes(value as ThemePreference)
}

/** A escolha salva; "system" se não houver, ou se o navegador bloquear o armazenamento. */
export function readThemePreference(storage?: Storage): ThemePreference {
  try {
    // Dentro do try: só acessar o localStorage já lança erro quando ele está bloqueado.
    const saved = (storage ?? localStorage).getItem(THEME_STORAGE_KEY)
    return isPreference(saved) ? saved : 'system'
  } catch {
    return 'system'
  }
}

export function saveThemePreference(preference: ThemePreference, storage?: Storage): void {
  try {
    const store = storage ?? localStorage
    if (preference === 'system') store.removeItem(THEME_STORAGE_KEY)
    else store.setItem(THEME_STORAGE_KEY, preference)
  } catch {
    // Armazenamento bloqueado (ex.: navegação privada): vale só até recarregar a página.
  }
}

export function applyThemePreference(
  preference: ThemePreference,
  root: HTMLElement = document.documentElement,
): void {
  if (preference === 'system') delete root.dataset.theme
  else root.dataset.theme = preference
}
