import { type KeyboardEvent, useEffect, useId, useRef, useState } from 'react'

import { useBrand } from '@/shared/brand/brand-context'
import { cx } from '@/shared/cx'
import { describeError } from '@/shared/http/describe-error'
import ui from '@/styles/ui.module.css'

import { useSession } from '../session-context'
import styles from './LoginPage.module.css'
import { NeuralBackdrop } from './NeuralBackdrop'
import { TypingDemo } from './TypingDemo'
import { type BotMood, type Gaze, VisorBot } from './VisorBot'

type Focus = 'username' | 'password' | null

const BOT_LINES: Record<BotMood, string> = {
  watching: 'Olá! Pronto para consultar os manuais?',
  shy: 'Pode digitar, não estou olhando.',
  peek: 'Opa… só uma espiadinha.',
  thinking: 'Conferindo suas credenciais…',
  happy: 'Tudo certo, é só entrar!',
  error: 'Hmm, algo não bateu. Vamos tentar de novo?',
}

export function LoginPage({ notice }: { readonly notice?: string | undefined }) {
  const brand = useBrand()
  const { login } = useSession()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  // Estado só visual: alimenta o robô e os detalhes do formulário.
  const [focus, setFocus] = useState<Focus>(null)
  const [showPassword, setShowPassword] = useState(false)
  const [capsLock, setCapsLock] = useState(false)
  const [aimingSubmit, setAimingSubmit] = useState(false)
  const [upset, setUpset] = useState(false)
  const [shakes, setShakes] = useState(0)

  const usernameId = useId()
  const passwordId = useId()
  const screenRef = usePointerParallax()

  const submit = async () => {
    setSubmitting(true)
    setError(null)
    try {
      await login(username.trim(), password)
    } catch (caught) {
      setError(describeError(caught))
      setPassword('')
      setSubmitting(false)
      setUpset(true)
      setShakes((n) => n + 1)
    }
  }

  const mood: BotMood = submitting
    ? 'thinking'
    : upset
      ? 'error'
      : focus === 'password'
        ? showPassword
          ? 'peek'
          : 'shy'
        : aimingSubmit && username && password
          ? 'happy'
          : 'watching'

  // Enquanto o usuário digita o login, o robô "lê" o campo da esquerda para a direita.
  const gaze: Gaze | undefined =
    focus === 'username' && mood === 'watching'
      ? { x: -0.9 + (Math.min(username.length, 24) / 24) * 1.8, y: 0.9 }
      : undefined

  const line =
    mood === 'watching' && focus === 'username'
      ? username.trim()
        ? `Oi, ${username.trim()}!`
        : 'Qual é o seu usuário do TOTVS?'
      : BOT_LINES[mood]

  const trackCapsLock = (event: KeyboardEvent<HTMLInputElement>) => {
    setCapsLock(event.getModifierState('CapsLock'))
  }

  return (
    <div className={styles.screen} ref={screenRef}>
      <NeuralBackdrop />
      <div className={styles.spotlight} aria-hidden="true" />

      <div className={styles.layout}>
        <section className={styles.hero}>
          <h1 className={styles.brand}>
            <BrandMark name={brand.name} logoUrl={brand.logoUrl} />
          </h1>
          <p className={styles.headline}>
            Pergunte. <span>Os manuais respondem.</span>
          </p>
          <p className={styles.tagline}>{brand.tagline}</p>
          <TypingDemo examples={brand.examples} />
          <ul className={styles.features}>
            <li>
              <FeatureIcon d="M4 2.5h6l3.5 3.5v9.5h-9.5zM10 2.5V6h3.5M6.5 9.5h4.5M6.5 12h3" />
              Respostas com a fonte citada
            </li>
            <li>
              <FeatureIcon d="M7.5 13a5.5 5.5 0 1 1 0-11 5.5 5.5 0 0 1 0 11zM11.5 11.5 15 15" />
              Busca em todos os manuais
            </li>
            <li>
              <FeatureIcon d="M4.5 7.5V5.5a3.5 3.5 0 0 1 7 0v2M3 7.5h10v7H3zM8 10.5v1.5" />
              Acesso com seu login TOTVS
            </li>
          </ul>
        </section>

        <form
          key={shakes}
          className={cx(styles.card, shakes > 0 && styles.shake)}
          onSubmit={(event) => {
            event.preventDefault()
            void submit()
          }}
        >
          <div className={styles.botArea}>
            <VisorBot mood={mood} gaze={gaze} className={styles.bot} />
            <p key={line} className={styles.bubble} aria-hidden="true">
              {line}
            </p>
          </div>

          <div className={styles.cardHeader}>
            <h2 className={styles.title}>Acesse sua conta</h2>
            <p className={styles.subtitle}>
              Entre com seu usuário e senha do TOTVS para consultar os manuais.
            </p>
          </div>

          {notice && !error && (
            <p className={ui.alert} data-tone="info" role="status">
              {notice}
            </p>
          )}
          {error && (
            <p className={ui.alert} data-tone="danger" role="alert">
              {error}
            </p>
          )}

          <div className={styles.field}>
            <input
              id={usernameId}
              className={styles.input}
              value={username}
              placeholder=" "
              onChange={(event) => {
                setUsername(event.target.value)
                setUpset(false)
              }}
              onFocus={() => {
                setFocus('username')
              }}
              onBlur={() => {
                setFocus(null)
              }}
              autoComplete="username"
              autoCapitalize="none"
              spellCheck={false}
              required
            />
            <label htmlFor={usernameId} className={styles.label}>
              Usuário
            </label>
            <FieldIcon d="M8 8.5a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM2.5 15c.6-3 2.8-4.5 5.5-4.5s4.9 1.5 5.5 4.5" />
          </div>

          <div className={styles.field}>
            <input
              id={passwordId}
              className={cx(styles.input, styles.withToggle)}
              type={showPassword ? 'text' : 'password'}
              value={password}
              placeholder=" "
              onChange={(event) => {
                setPassword(event.target.value)
                setUpset(false)
              }}
              onFocus={() => {
                setFocus('password')
              }}
              onBlur={() => {
                setFocus(null)
                setCapsLock(false)
              }}
              onKeyDown={trackCapsLock}
              onKeyUp={trackCapsLock}
              autoComplete="current-password"
              required
            />
            <label htmlFor={passwordId} className={styles.label}>
              Senha
            </label>
            <FieldIcon d="M4.5 7.5V5.5a3.5 3.5 0 0 1 7 0v2M3 7.5h10v7H3zM8 10.5v1.5" />
            <button
              type="button"
              className={styles.toggle}
              aria-label={showPassword ? 'Ocultar senha' : 'Mostrar senha'}
              aria-pressed={showPassword}
              // Mantém o foco na senha: o robô continua "espiando" em vez de voltar a olhar.
              onMouseDown={(event) => {
                event.preventDefault()
              }}
              onClick={() => {
                setShowPassword((shown) => !shown)
              }}
            >
              <svg viewBox="0 0 16 16" aria-hidden="true">
                <path d="M1 8s2.6-4.5 7-4.5S15 8 15 8s-2.6 4.5-7 4.5S1 8 1 8z" />
                <circle cx="8" cy="8" r="2" />
                {!showPassword && <path d="M2.5 13.5l11-11" />}
              </svg>
            </button>
          </div>

          {capsLock && (
            <p className={styles.capsLock} role="status">
              Caps Lock está ativado.
            </p>
          )}

          <button
            className={styles.submit}
            type="submit"
            disabled={submitting}
            onPointerEnter={() => {
              setAimingSubmit(true)
            }}
            onPointerLeave={() => {
              setAimingSubmit(false)
            }}
            onFocus={() => {
              setAimingSubmit(true)
            }}
            onBlur={() => {
              setAimingSubmit(false)
            }}
          >
            {submitting && <span className={styles.spinner} aria-hidden="true" />}
            {submitting ? 'Entrando…' : 'Entrar'}
            {!submitting && (
              <svg className={styles.arrow} viewBox="0 0 16 16" aria-hidden="true">
                <path d="M3 8h10M9 4l4 4-4 4" />
              </svg>
            )}
          </button>

          <p className={styles.hint}>
            Esqueceu a senha? Redefina-a no TOTVS. Se o seu usuário foi criado aqui, peça a um
            administrador.
          </p>
        </form>
      </div>
    </div>
  )
}

/** Logo da marca, ou o nome com a última palavra em destaque se não houver logo. */
function BrandMark({ name, logoUrl }: { readonly name: string; readonly logoUrl: string | null }) {
  const [broken, setBroken] = useState(false)
  if (logoUrl && !broken) {
    return (
      <img
        className={styles.logo}
        src={logoUrl}
        alt={name}
        onError={() => {
          setBroken(true)
        }}
      />
    )
  }
  const words = name.split(' ')
  const last = words.pop()
  return (
    <span className={styles.wordmark}>
      {words.length > 0 && `${words.join(' ')} `}
      <span>{last}</span>
    </span>
  )
}

function FieldIcon({ d }: { readonly d: string }) {
  return (
    <svg className={styles.fieldIcon} viewBox="0 0 16 16" aria-hidden="true">
      <path d={d} />
    </svg>
  )
}

function FeatureIcon({ d }: { readonly d: string }) {
  return (
    <span className={styles.featureIcon} aria-hidden="true">
      <svg viewBox="0 0 16 16">
        <path d={d} />
      </svg>
    </span>
  )
}

/**
 * Publica a posição do ponteiro como variáveis CSS (--px/--py em pixels e
 * --nx/--ny de -1 a 1), usadas pelo holofote e pela inclinação da logo,
 * sem re-renderizar o React a cada movimento.
 */
function usePointerParallax() {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const element = ref.current
    if (!element) return
    let frame = 0
    const onMove = (event: PointerEvent) => {
      cancelAnimationFrame(frame)
      frame = requestAnimationFrame(() => {
        const { innerWidth: w, innerHeight: h } = window
        element.style.setProperty('--px', `${String(event.clientX)}px`)
        element.style.setProperty('--py', `${String(event.clientY)}px`)
        element.style.setProperty('--nx', ((event.clientX / w) * 2 - 1).toFixed(3))
        element.style.setProperty('--ny', ((event.clientY / h) * 2 - 1).toFixed(3))
      })
    }
    window.addEventListener('pointermove', onMove)
    return () => {
      cancelAnimationFrame(frame)
      window.removeEventListener('pointermove', onMove)
    }
  }, [])
  return ref
}
