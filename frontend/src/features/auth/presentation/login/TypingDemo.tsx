import { useEffect, useState } from 'react'

import styles from './LoginPage.module.css'

type Phase = 'typing' | 'answering' | 'answered' | 'erasing'

/**
 * Só anima num navegador de verdade (o jsdom dos testes não tem matchMedia).
 * A digitação é lenta e informativa, então continua mesmo com "reduzir movimento".
 */
function canAnimate(): boolean {
  return typeof window.matchMedia === 'function'
}

/**
 * Prévia do assistente na tela de login: digita uma pergunta de exemplo,
 * "pensa", mostra a resposta com a fonte e passa para a próxima.
 */
export function TypingDemo({ examples }: { readonly examples: readonly string[] }) {
  const [animated] = useState(canAnimate)
  const [index, setIndex] = useState(0)
  const [length, setLength] = useState(() => (animated ? 0 : Infinity))
  const [phase, setPhase] = useState<Phase>(animated ? 'typing' : 'answered')

  const question = examples[index % examples.length] ?? ''

  useEffect(() => {
    if (!animated) return
    const after = (ms: number, fn: () => void) => {
      const id = window.setTimeout(fn, ms)
      return () => {
        window.clearTimeout(id)
      }
    }
    switch (phase) {
      case 'typing':
        return length < question.length
          ? after(28 + Math.random() * 45, () => {
              setLength((n) => n + 1)
            })
          : after(450, () => {
              setPhase('answering')
            })
      case 'answering':
        return after(1100, () => {
          setPhase('answered')
        })
      case 'answered':
        return after(2800, () => {
          setPhase('erasing')
        })
      case 'erasing':
        return length > 0
          ? after(14, () => {
              setLength((n) => Math.max(0, n - 2))
            })
          : after(300, () => {
              setIndex((i) => i + 1)
              setPhase('typing')
            })
    }
  }, [animated, phase, length, question.length])

  const showAnswer = phase === 'answering' || phase === 'answered'

  return (
    <div className={styles.demo} aria-hidden="true">
      <div className={styles.demoQuestion}>
        <span>{question.slice(0, length)}</span>
        {(phase === 'typing' || phase === 'erasing') && <span className={styles.caret} />}
      </div>
      <div className={styles.demoAnswer} data-visible={showAnswer} data-phase={phase}>
        {phase === 'answering' ? (
          <span className={styles.dots}>
            <i />
            <i />
            <i />
          </span>
        ) : (
          <>
            <span className={styles.skeleton} style={{ width: '92%' }} />
            <span className={styles.skeleton} style={{ width: '78%' }} />
            <span className={styles.skeleton} style={{ width: '55%' }} />
            <span className={styles.source}>
              <svg viewBox="0 0 16 16" aria-hidden="true">
                <path d="M4 1.5h5.5L13 5v9.5H4z" />
                <path d="M9.5 1.5V5H13M6.5 8.5h4M6.5 11h4" />
              </svg>
              Resposta com a página do manual
            </span>
          </>
        )}
      </div>
    </div>
  )
}
