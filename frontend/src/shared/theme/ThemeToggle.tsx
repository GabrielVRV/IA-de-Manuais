import { type ReactNode, useState } from 'react'

import {
  applyThemePreference,
  readThemePreference,
  saveThemePreference,
  THEME_PREFERENCES,
  type ThemePreference,
} from './theme'
import styles from './ThemeToggle.module.css'

const LABELS: Record<ThemePreference, string> = {
  system: 'Tema do sistema',
  light: 'Tema claro',
  dark: 'Tema escuro',
}

const ICON_PROPS = {
  width: 16,
  height: 16,
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 2,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
  'aria-hidden': true,
} as const

const ICONS: Record<ThemePreference, ReactNode> = {
  system: (
    <svg {...ICON_PROPS}>
      <rect x="3" y="4" width="18" height="12" rx="2" />
      <path d="M8 20h8M12 16v4" />
    </svg>
  ),
  light: (
    <svg {...ICON_PROPS}>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
    </svg>
  ),
  dark: (
    <svg {...ICON_PROPS}>
      <path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5Z" />
    </svg>
  ),
}

/** Escolha entre o tema do sistema, claro ou escuro, lembrada neste navegador. */
export function ThemeToggle() {
  const [preference, setPreference] = useState<ThemePreference>(() => readThemePreference())

  const choose = (next: ThemePreference) => {
    setPreference(next)
    saveThemePreference(next)
    applyThemePreference(next)
  }

  return (
    <div className={styles.toggle} role="group" aria-label="Tema">
      {THEME_PREFERENCES.map((option) => (
        <button
          key={option}
          type="button"
          className={styles.option}
          aria-pressed={preference === option}
          aria-label={LABELS[option]}
          title={LABELS[option]}
          onClick={() => {
            choose(option)
          }}
        >
          {ICONS[option]}
        </button>
      ))}
    </div>
  )
}
