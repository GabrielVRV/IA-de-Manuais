import styles from './ApiStatus.module.css'
import { type ApiHealthState, useApiHealth } from './use-api-health'

type Tone = 'neutral' | 'success' | 'warning' | 'danger'

interface StatusView {
  readonly tone: Tone
  readonly title: string
  readonly detail: string
}

function toView(state: ApiHealthState): StatusView {
  switch (state.kind) {
    case 'checking':
      return { tone: 'neutral', title: 'Verificando o servidor…', detail: 'Aguarde um instante.' }
    case 'unreachable':
      return { tone: 'danger', title: 'Servidor indisponível', detail: state.message }
    case 'reachable': {
      const { health } = state
      if (health.status === 'up') {
        return { tone: 'success', title: 'Servidor online', detail: `Versão ${health.version}` }
      }
      const failing = Object.entries(health.components)
        .filter(([, status]) => status === 'down')
        .map(([name]) => name)
      return {
        tone: 'warning',
        title: 'Servidor com instabilidade',
        detail: `Componentes fora do ar: ${failing.join(', ')}`,
      }
    }
  }
}

export function ApiStatus() {
  const { state, recheck } = useApiHealth()
  const view = toView(state)
  const isChecking = state.kind === 'checking'

  return (
    <section className={styles.card} data-tone={view.tone} aria-labelledby="api-status-title">
      <span className={styles.indicator} aria-hidden="true" />
      <div className={styles.text} role="status" aria-live="polite">
        <h2 id="api-status-title" className={styles.title}>
          {view.title}
        </h2>
        <p className={styles.detail}>{view.detail}</p>
      </div>
      <button type="button" className={styles.button} onClick={recheck} disabled={isChecking}>
        Verificar novamente
      </button>
    </section>
  )
}
