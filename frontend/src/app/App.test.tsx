import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { HealthGateway } from '@/features/health/domain/api-health'
import { HealthGatewayContext } from '@/features/health/presentation/health-gateway-context'

import { App } from './App'

const healthyGateway: HealthGateway = {
  check: () => Promise.resolve({ status: 'up', version: '0.1.0', components: {} }),
}

describe('<App />', () => {
  it('renders the shell with the API status', async () => {
    render(
      <HealthGatewayContext value={healthyGateway}>
        <App />
      </HealthGatewayContext>,
    )

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Assistente de Manuais')
    expect(await screen.findByText('Servidor online')).toBeInTheDocument()
  })
})
