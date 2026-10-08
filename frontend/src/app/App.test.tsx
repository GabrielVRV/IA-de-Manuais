import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { QuestionGateway } from '@/features/chat/domain/chat'
import { QuestionGatewayContext } from '@/features/chat/presentation/question-gateway-context'
import type { HealthGateway } from '@/features/health/domain/api-health'
import { HealthGatewayContext } from '@/features/health/presentation/health-gateway-context'

import { App } from './App'

const healthyGateway: HealthGateway = {
  check: () => Promise.resolve({ status: 'up', version: '0.1.0', components: {} }),
}

const questionGateway: QuestionGateway = {
  ask: () => Promise.resolve({ text: 'ok', found: true, citations: [] }),
  sourceUrl: () => '#',
}

describe('<App />', () => {
  it('renders the shell with the server status and the chat', async () => {
    render(
      <HealthGatewayContext value={healthyGateway}>
        <QuestionGatewayContext value={questionGateway}>
          <App />
        </QuestionGatewayContext>
      </HealthGatewayContext>,
    )

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Assistente de Manuais')
    expect(await screen.findByText('Online')).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: /sua pergunta/i })).toBeInTheDocument()
  })
})
