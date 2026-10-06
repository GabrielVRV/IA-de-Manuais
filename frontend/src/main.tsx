/**
 * Raiz de composição: lê a configuração, cria os adaptadores concretos e os
 * injeta na árvore React. É o único arquivo que conhece a infraestrutura.
 */
import './styles/global.css'

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import { App } from '@/app/App'
import { loadRuntimeConfig } from '@/app/config/runtime-config'
import { StartupError } from '@/app/StartupError'
import { HttpHealthGateway } from '@/features/health/infrastructure/http-health-gateway'
import { HealthGatewayContext } from '@/features/health/presentation/health-gateway-context'
import { HttpClient } from '@/shared/http/http-client'

async function bootstrap(): Promise<void> {
  const container = document.getElementById('root')
  if (!container) throw new Error('Elemento #root não encontrado no index.html')
  const root = createRoot(container)

  try {
    const config = await loadRuntimeConfig()
    const http = new HttpClient(config.apiBaseUrl)

    root.render(
      <StrictMode>
        <HealthGatewayContext value={new HttpHealthGateway(http)}>
          <App />
        </HealthGatewayContext>
      </StrictMode>,
    )
  } catch (error) {
    root.render(
      <StrictMode>
        <StartupError error={error} />
      </StrictMode>,
    )
  }
}

void bootstrap()
