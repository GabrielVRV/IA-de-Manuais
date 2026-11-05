import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { fakeUsageGateway, REGULAR, FakeAuthGateway, renderApp, usageReport } from '@/test/fakes'

import { formatUsd } from './format-usd'

describe('<UsageReport />', () => {
  it('shows the totals and ranks who used the assistant the most', async () => {
    renderApp({ path: '/admin/consumo' })

    const table = await screen.findByRole('table', { name: 'Consumo por usuário' })
    const rows = within(table).getAllByRole('row').slice(1)

    expect(rows[0]).toHaveTextContent('Maria Silva')
    expect(rows[0]).toHaveTextContent('33.000')
    expect(rows[1]).toHaveTextContent('João')
    expect(screen.getByText('42.900')).toBeInTheDocument()
    expect(screen.getByText('Custo estimado')).toBeInTheDocument()
  })

  it('reloads the report when the period changes', async () => {
    const usage = fakeUsageGateway()
    renderApp({ path: '/admin/consumo', usage })
    await screen.findByText('Quem mais usou')

    await userEvent.setup().selectOptions(screen.getByRole('combobox'), 'Últimos 7 dias')

    expect(usage.report).toHaveBeenLastCalledWith(7)
  })

  it('warns about models without price and hides the cost when none is priced', async () => {
    const report = usageReport({
      unpricedModels: ['gpt-4.1-mini'],
      byModel: [
        {
          model: 'gpt-4.1-mini',
          priced: false,
          totals: usageReport().totals,
        },
      ],
    })
    renderApp({ path: '/admin/consumo', usage: fakeUsageGateway(report) })

    const warning = (await screen.findByText(/Sem preço cadastrado/)).closest('p')
    if (!warning) throw new Error('aviso não encontrado')

    expect(warning).toHaveTextContent('Sem preço cadastrado: gpt-4.1-mini')
    expect(within(warning).getByRole('link')).toHaveAttribute('href', '/admin/configuracoes')
    expect(screen.queryByText('Custo estimado')).not.toBeInTheDocument()
  })

  it('draws one bar per day of the period', async () => {
    renderApp({ path: '/admin/consumo' })

    const bars = await screen.findByRole('list', { name: 'Tokens por dia' })

    expect(within(bars).getAllByRole('listitem')).toHaveLength(7)
    expect(within(bars).getByLabelText(/^05\/11: 33\.000 tokens/)).toBeInTheDocument()
  })

  it('is only reachable by admins', async () => {
    renderApp({ path: '/admin/consumo', auth: new FakeAuthGateway(REGULAR) })

    await screen.findByRole('textbox')
    expect(screen.queryByRole('link', { name: 'Consumo' })).not.toBeInTheDocument()
    expect(screen.queryByText('Quem mais usou')).not.toBeInTheDocument()
  })
})

describe('formatUsd', () => {
  it('keeps more decimals for fractions of a dollar', () => {
    // O Intl separa o símbolo com espaço não separável.
    const plain = (value: number) => formatUsd(value).replace(/\s/g, ' ')
    expect(plain(0.0168)).toBe('US$ 0,0168')
    expect(plain(12.5)).toBe('US$ 12,50')
    expect(plain(0)).toBe('US$ 0,00')
  })
})
