import { type CSSProperties, useEffect, useRef } from 'react'

import { cx } from '@/shared/cx'

import styles from './VisorBot.module.css'

/**
 * Humor do robô da tela de login:
 * - `watching`: olha para o cursor (ou para onde `gaze` mandar);
 * - `shy`: olhos fechados enquanto a senha é digitada;
 * - `peek`: espia com um olho quando a senha está visível;
 * - `thinking`, `happy` e `error`: aguardando o servidor, pronto para entrar e falha.
 */
export type BotMood = 'watching' | 'shy' | 'peek' | 'thinking' | 'happy' | 'error'

/** Direção do olhar, de -1 a 1 em cada eixo. */
export interface Gaze {
  readonly x: number
  readonly y: number
}

interface VisorBotProps {
  readonly mood: BotMood
  /** Sem `gaze`, o robô acompanha o ponteiro do mouse. */
  readonly gaze?: Gaze | undefined
  readonly className?: string | undefined
}

const clamp = (value: number) => Math.max(-1, Math.min(1, value))

export function VisorBot({ mood, gaze, className }: VisorBotProps) {
  const ref = useRef<SVGSVGElement>(null)
  const followPointer = gaze === undefined

  useEffect(() => {
    const svg = ref.current
    if (!svg || !followPointer) return
    let frame = 0
    const onMove = (event: PointerEvent) => {
      cancelAnimationFrame(frame)
      frame = requestAnimationFrame(() => {
        const box = svg.getBoundingClientRect()
        const x = (event.clientX - (box.left + box.width / 2)) / (window.innerWidth / 2)
        const y = (event.clientY - (box.top + box.height / 2)) / (window.innerHeight / 2)
        svg.style.setProperty('--gx', String(clamp(x * 1.6)))
        svg.style.setProperty('--gy', String(clamp(y * 1.6)))
      })
    }
    window.addEventListener('pointermove', onMove)
    return () => {
      cancelAnimationFrame(frame)
      window.removeEventListener('pointermove', onMove)
    }
  }, [followPointer])

  const style = gaze ? ({ '--gx': gaze.x, '--gy': gaze.y } as CSSProperties) : undefined

  return (
    <svg
      ref={ref}
      className={cx(styles.bot, className)}
      viewBox="0 0 160 128"
      data-mood={mood}
      style={style}
      aria-hidden="true"
      focusable="false"
    >
      <defs>
        <linearGradient id="bot-shell" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#ffffff" />
          <stop offset="1" stopColor="#cfdcf2" />
        </linearGradient>
        <linearGradient id="bot-visor" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#0b1d4a" />
          <stop offset="1" stopColor="#020a24" />
        </linearGradient>
        <filter id="bot-glow" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="2.4" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>

      {/* Fones de ouvido */}
      <g className={styles.ears}>
        <rect x="6" y="44" width="22" height="40" rx="11" />
        <rect x="132" y="44" width="22" height="40" rx="11" />
        <rect className={styles.earLight} x="12" y="54" width="6" height="20" rx="3" />
        <rect className={styles.earLight} x="142" y="54" width="6" height="20" rx="3" />
      </g>

      {/* Cabeça e visor */}
      <rect x="20" y="10" width="120" height="108" rx="44" fill="url(#bot-shell)" />
      <rect x="32" y="24" width="96" height="78" rx="32" fill="url(#bot-visor)" />
      <path className={styles.gloss} d="M46 34 Q80 26 114 34" />

      <g className={styles.eyes} filter="url(#bot-glow)">
        {/* Olhos abertos: acompanham o olhar e piscam de vez em quando */}
        <g className={styles.look}>
          <g className={styles.open}>
            <rect className={styles.blink} x="53" y="51" width="13" height="20" rx="6.5" />
            <rect className={styles.blink} x="94" y="51" width="13" height="20" rx="6.5" />
          </g>
          {/* Espiando: só o olho direito aberto */}
          <rect className={styles.peekEye} x="94" y="51" width="13" height="20" rx="6.5" />
        </g>
        {/* Olhos fechados (senha) */}
        <g className={styles.closed}>
          <path d="M51 62 Q59.5 69 68 62" />
          <path className={styles.peekHide} d="M92 62 Q100.5 69 109 62" />
        </g>
        {/* Feliz: os arcos do mascote */}
        <g className={styles.happy}>
          <path d="M50 66 Q59.5 50 69 66" />
          <path d="M91 66 Q100.5 50 110 66" />
        </g>
        {/* Erro */}
        <g className={styles.error}>
          <path d="M53 53 L66 61 L53 69" />
          <path d="M107 53 L94 61 L107 69" />
        </g>
      </g>
    </svg>
  )
}
