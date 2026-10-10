/**
 * Raiz de composição: lê a configuração, cria os adaptadores concretos e os
 * injeta na árvore React. É o único arquivo que conhece a infraestrutura.
 */
import './styles/global.css'

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { HashRouter } from 'react-router'

import { App } from '@/app/App'
import { loadRuntimeConfig } from '@/app/config/runtime-config'
import { StartupError } from '@/app/StartupError'
import { HttpAuthGateway } from '@/features/auth/infrastructure/http-auth-gateway'
import { AuthGatewayContext } from '@/features/auth/presentation/session-context'
import { SessionProvider } from '@/features/auth/presentation/SessionProvider'
import { HttpQuestionGateway } from '@/features/chat/infrastructure/http-question-gateway'
import { QuestionGatewayContext } from '@/features/chat/presentation/question-gateway-context'
import { HttpHealthGateway } from '@/features/health/infrastructure/http-health-gateway'
import { HealthGatewayContext } from '@/features/health/presentation/health-gateway-context'
import { HttpManualsGateway } from '@/features/manuals/infrastructure/http-manuals-gateway'
import { ManualsGatewayContext } from '@/features/manuals/presentation/manuals-gateway-context'
import { HttpUsersGateway } from '@/features/users/infrastructure/http-users-gateway'
import { UsersGatewayContext } from '@/features/users/presentation/users-gateway-context'
import { applyBrand, loadBrand } from '@/shared/brand/brand'
import { BrandContext } from '@/shared/brand/brand-context'
import { HttpClient } from '@/shared/http/http-client'

async function bootstrap(): Promise<void> {
  const container = document.getElementById('root')
  if (!container) throw new Error('Elemento #root não encontrado no index.html')
  const root = createRoot(container)

  try {
    // A marca é opcional: loadBrand nunca falha, então não impede a aplicação de abrir.
    const [config, brand] = await Promise.all([loadRuntimeConfig(), loadBrand()])
    applyBrand(brand)
    const http = new HttpClient(config.apiBaseUrl)

    root.render(
      <StrictMode>
        <BrandContext value={brand}>
          <AuthGatewayContext value={new HttpAuthGateway(http)}>
            <HealthGatewayContext value={new HttpHealthGateway(http)}>
              <QuestionGatewayContext value={new HttpQuestionGateway(http)}>
                <ManualsGatewayContext value={new HttpManualsGateway(http)}>
                  <UsersGatewayContext value={new HttpUsersGateway(http)}>
                    <SessionProvider>
                      {/* Rotas por "#": funcionam em qualquer subpasta do XAMPP sem reescrita. */}
                      <HashRouter>
                        <App />
                      </HashRouter>
                    </SessionProvider>
                  </UsersGatewayContext>
                </ManualsGatewayContext>
              </QuestionGatewayContext>
            </HealthGatewayContext>
          </AuthGatewayContext>
        </BrandContext>
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
