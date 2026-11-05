import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { fakeAssistantsGateway, FakeAuthGateway, REGULAR, renderApp } from '@/test/fakes'

describe('<AccessAdmin />', () => {
  it('restricts the assistant and saves how to ask for access', async () => {
    const assistants = fakeAssistantsGateway()
    const user = userEvent.setup()
    renderApp({ assistants, path: '/admin/acessos' })

    const form = await screen.findByRole('form', { name: 'Assistente de Engenharia' })
    expect(within(form).getByRole('radio', { name: /Liberado para todos/ })).toBeChecked()

    await user.click(within(form).getByRole('radio', { name: /Só para quem for liberado/ }))
    await user.type(
      within(form).getByLabelText('Como pedir acesso'),
      'Abra um chamado no GLPI pedindo acesso.',
    )
    await user.click(within(form).getByRole('button', { name: 'Salvar acesso' }))

    expect(assistants.updatePolicy).toHaveBeenCalledWith('engenharia', {
      defaultAccess: 'restricted',
      requestInstructions: 'Abra um chamado no GLPI pedindo acesso.',
    })
    expect(await screen.findByText('Acesso ao Assistente de Engenharia salvo.')).toBeInTheDocument()
    expect(screen.getByText(/Alterado por Ana Admin/)).toBeInTheDocument()
  })

  it('sends blank instructions as the default message', async () => {
    const assistants = fakeAssistantsGateway()
    const user = userEvent.setup()
    renderApp({ assistants, path: '/admin/acessos' })

    await user.type(await screen.findByLabelText('Como pedir acesso'), '   ')
    await user.click(screen.getByRole('button', { name: 'Salvar acesso' }))

    expect(assistants.updatePolicy).toHaveBeenCalledWith('engenharia', {
      defaultAccess: 'open',
      requestInstructions: null,
    })
  })

  it('is only reachable by admins', async () => {
    renderApp({ path: '/admin/acessos', auth: new FakeAuthGateway(REGULAR) })

    await screen.findByRole('textbox', { name: /sua pergunta/i })
    expect(screen.queryByRole('heading', { name: 'Acessos' })).not.toBeInTheDocument()
  })
})
