import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { NetworkError } from '@/shared/http/errors'

import type { ApiHealth, HealthGateway } from '../domain/api-health'
import { ApiStatus } from './ApiStatus'
import { HealthGatewayContext } from './health-gateway-context'

const renderWith = (gateway: HealthGateway) =>
  render(
    <HealthGatewayContext value={gateway}>
      <ApiStatus />
    </HealthGatewayContext>,
  )

const gatewayResolving = (health: ApiHealth): HealthGateway => ({
  check: () => Promise.resolve(health),
})

describe('<ApiStatus />', () => {
  it('shows the API as online with its version', async () => {
    renderWith(gatewayResolving({ status: 'up', version: '0.1.0', components: {} }))

    expect(await screen.findByText('Servidor online')).toBeInTheDocument()
    expect(screen.getByText('Versão 0.1.0')).toBeInTheDocument()
  })

  it('lists the components that are down', async () => {
    renderWith(
      gatewayResolving({
        status: 'down',
        version: '0.1.0',
        components: { database: 'down', llm: 'up' },
      }),
    )

    expect(await screen.findByText('Servidor com instabilidade')).toBeInTheDocument()
    expect(screen.getByText('Componentes fora do ar: database')).toBeInTheDocument()
  })

  it('explains when the API cannot be reached and allows a new check', async () => {
    const check = vi
      .fn<HealthGateway['check']>()
      .mockRejectedValueOnce(new NetworkError())
      .mockResolvedValueOnce({ status: 'up', version: '0.1.0', components: {} })
    renderWith({ check })

    expect(await screen.findByText('Servidor indisponível')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Verificar novamente' }))

    expect(await screen.findByText('Servidor online')).toBeInTheDocument()
    expect(check).toHaveBeenCalledTimes(2)
  })
})
