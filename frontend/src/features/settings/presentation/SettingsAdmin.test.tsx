import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { fakeSettingsGateway, FakeAuthGateway, REGULAR, renderApp } from '@/test/fakes'

import { parsePrice } from './price-text'

const unpriced = {
  model: 'gpt-4.1-mini',
  configured: false,
  inputPerMillion: null,
  outputPerMillion: null,
}

function setup(prices = [unpriced]) {
  const settings = fakeSettingsGateway(prices)
  renderApp({ path: '/configuracoes', settings })
  return { settings, user: userEvent.setup() }
}

describe('<SettingsAdmin />', () => {
  it('changes the usage retention', async () => {
    const { settings, user } = setup()
    const months = await screen.findByLabelText('Meses')

    await user.clear(months)
    await user.type(months, '6')
    await user.click(screen.getByRole('button', { name: 'Salvar' }))

    expect(settings.update).toHaveBeenCalledWith({ usageRetentionMonths: 6 })
    expect(await screen.findByText('Retenção do consumo salva.')).toBeInTheDocument()
    expect(screen.getByText(/Alterado por Ana Admin/)).toBeInTheDocument()
  })

  it('prices a model already used, accepting a comma as decimal separator', async () => {
    const { settings, user } = setup()
    expect(await screen.findByText('Sem preço')).toBeInTheDocument()

    await user.type(screen.getByLabelText('Preço de entrada de gpt-4.1-mini'), '0,40')
    await user.type(screen.getByLabelText('Preço de saída de gpt-4.1-mini'), '1,6')
    await user.click(screen.getByRole('button', { name: 'Salvar o preço de gpt-4.1-mini' }))

    expect(settings.setModelPrice).toHaveBeenCalledWith({
      model: 'gpt-4.1-mini',
      inputPerMillion: 0.4,
      outputPerMillion: 1.6,
    })
    expect(await screen.findByText('Preço de gpt-4.1-mini salvo.')).toBeInTheDocument()
    expect(screen.queryByText('Sem preço')).not.toBeInTheDocument()
  })

  it('adds the price of another model and removes it', async () => {
    const { settings, user } = setup([])
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    await user.type(await screen.findByLabelText('Outro modelo'), 'gpt-5-mini')
    await user.type(screen.getByLabelText('Entrada (US$/milhão)'), '0.25')
    await user.type(screen.getByLabelText('Saída (US$/milhão)'), '2')

    await user.click(screen.getByRole('button', { name: 'Adicionar' }))

    expect(await screen.findByLabelText('Preço de entrada de gpt-5-mini')).toHaveValue('0,25')

    await user.click(screen.getByRole('button', { name: 'Remover o preço de gpt-5-mini' }))

    expect(settings.deleteModelPrice).toHaveBeenCalledWith('gpt-5-mini')
    expect(await screen.findByText('Preço de gpt-5-mini removido.')).toBeInTheDocument()
  })

  it('does not save an invalid price', async () => {
    const { user } = setup()

    await user.type(await screen.findByLabelText('Preço de entrada de gpt-4.1-mini'), 'abc')
    await user.type(screen.getByLabelText('Preço de saída de gpt-4.1-mini'), '1')

    expect(screen.getByRole('button', { name: 'Salvar o preço de gpt-4.1-mini' })).toBeDisabled()
  })

  it('is only reachable by admins', async () => {
    renderApp({ path: '/configuracoes', auth: new FakeAuthGateway(REGULAR) })

    await screen.findByRole('textbox')
    expect(screen.queryByRole('link', { name: 'Configurações' })).not.toBeInTheDocument()
    expect(screen.queryByText('Retenção do consumo')).not.toBeInTheDocument()
  })
})

describe('parsePrice', () => {
  it.each([
    ['0,40', 0.4],
    ['1.6', 1.6],
    [' 2 ', 2],
    ['', null],
    ['-1', null],
    ['1,2,3', null],
    ['abc', null],
  ])('reads %j as %j', (text, expected) => {
    expect(parsePrice(text)).toBe(expected)
  })
})
