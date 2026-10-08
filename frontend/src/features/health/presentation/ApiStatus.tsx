import styles from './ApiStatus.module.css'
import { type ApiHealthState, useApiHealth } from './use-api-health'

type Tone = 'neutral' | 'success' | 'warning' | 'danger'

interface StatusView {
  readonly tone: Tone
  readonly label: string
  readonly detail: string
}

function toView(state: ApiHealthState): StatusView {
  switch (state.kind) {
    case 'checking':
      return { tone: 'neutral', label: 'Verificando…', detail: 'Verificando o servidor.' }
    case 'unreachable':
      return { tone: 'danger', label: 'Offline', detail: state.message }
    case 'reachable': {
      const { health } = state
      if (health.status === 'up') {
        return {
          tone: 'success',
          label: 'Online',
          detail: `Servidor online, versão ${health.version}.`,
        }
      }
      const failing = Object.entries(health.components)
        .filter(([, status]) => status === 'down')
        .map(([name]) => name)
      return {
        tone: 'warning',
        label: 'Instável',
        detail: `Componentes fora do ar: ${failing.join(', ')}.`,
      }
    }
  }
}

/** Indicador compacto para o cabeçalho; clicar verifica de novo. */
export function ApiStatus() {
  const { state, recheck } = useApiHealth()
  const view = toView(state)

  return (
    <button
      type="button"
      className={styles.badge}
      data-tone={view.tone}
      onClick={recheck}
      disabled={state.kind === 'checking'}
      title={`${view.detail} Clique para verificar novamente.`}
    >
      <span className={styles.indicator} aria-hidden="true" />
      <span role="status" aria-live="polite">
        <span className={styles.visuallyHidden}>Servidor: </span>
        {view.label}
        <span className={styles.visuallyHidden}> — {view.detail}</span>
      </span>
    </button>
  )
}
