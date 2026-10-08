import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { HttpError, NetworkError } from '@/shared/http/errors'

import type { Answer, QuestionGateway } from '../domain/chat'
import { Chat } from './Chat'
import { QuestionGatewayContext } from './question-gateway-context'

const answer: Answer = {
  text: 'A pressão máxima é **10 bar** [fonte].',
  found: true,
  citations: [
    { manualId: 'cx500', manualTitle: 'Compressor CX-500', pages: [3, 4], pagesLabel: 'p. 3-4' },
  ],
}

const notFound: Answer = { text: 'Não encontrei essa informação.', found: false, citations: [] }

let ask: ReturnType<typeof vi.fn<QuestionGateway['ask']>>

function renderChat() {
  const gateway: QuestionGateway = {
    ask,
    sourceUrl: (citation) =>
      `http://api/manuals/${citation.manualId}/file#page=${String(citation.pages[0])}`,
  }
  return render(
    <QuestionGatewayContext value={gateway}>
      <Chat />
    </QuestionGatewayContext>,
  )
}

const input = () => screen.getByRole('textbox', { name: /sua pergunta/i })
const log = () => screen.getByRole('log')

beforeEach(() => {
  ask = vi.fn<QuestionGateway['ask']>().mockResolvedValue(answer)
})

describe('<Chat />', () => {
  it('asks with Enter and shows the formatted answer with a link to the cited page', async () => {
    const user = userEvent.setup()
    renderChat()

    await user.type(input(), 'Qual a pressão máxima?{Enter}')

    expect(within(log()).getByText('Qual a pressão máxima?')).toBeInTheDocument()
    expect(await screen.findByText('10 bar')).toContainHTML('<strong>10 bar</strong>')
    const source = screen.getByRole('link', { name: /Compressor CX-500/ })
    expect(source).toHaveAttribute('href', 'http://api/manuals/cx500/file#page=3')
    expect(source).toHaveAttribute('target', '_blank')
    expect(source).toHaveTextContent('p. 3-4')
    expect(input()).toHaveValue('')
    expect(ask).toHaveBeenCalledWith('Qual a pressão máxima?', expect.any(AbortSignal))
  })

  it('shows that it is working while waiting for the answer', async () => {
    let resolve!: (value: Answer) => void
    ask.mockReturnValue(new Promise((r) => (resolve = r)))
    const user = userEvent.setup()
    renderChat()

    await user.type(input(), 'Qual a pressão?{Enter}')

    expect(screen.getByText('Consultando os manuais…')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Perguntar' })).toBeDisabled()
    resolve(answer)
    expect(await screen.findByText('10 bar')).toBeInTheDocument()
    expect(screen.queryByText('Consultando os manuais…')).not.toBeInTheDocument()
  })

  it('uses Shift+Enter for a new line instead of sending', async () => {
    const user = userEvent.setup()
    renderChat()

    await user.type(input(), 'Linha um{Shift>}{Enter}{/Shift}linha dois')

    expect(input()).toHaveValue('Linha um\nlinha dois')
    expect(ask).not.toHaveBeenCalled()
  })

  it('does not send questions that are too short', async () => {
    const user = userEvent.setup()
    renderChat()

    await user.type(input(), 'oi{Enter}')

    expect(screen.getByRole('button', { name: 'Perguntar' })).toBeDisabled()
    expect(ask).not.toHaveBeenCalled()
  })

  it('asks a suggested question with one click', async () => {
    const user = userEvent.setup()
    renderChat()

    await user.click(screen.getByRole('button', { name: /troca de óleo/ }))

    expect(ask).toHaveBeenCalledWith(
      'Como fazer a troca de óleo, passo a passo?',
      expect.any(AbortSignal),
    )
  })

  it('marks answers that were not found in the manuals', async () => {
    ask.mockResolvedValue(notFound)
    const user = userEvent.setup()
    renderChat()

    await user.type(input(), 'Como faço um bolo?{Enter}')

    const bubble = (await screen.findByText('Não encontrei essa informação.')).closest('article')
    expect(bubble).toHaveAttribute('data-found', 'false')
    expect(screen.queryByText('Fontes')).not.toBeInTheDocument()
  })

  it('explains failures and retries without repeating the question', async () => {
    ask.mockRejectedValueOnce(new HttpError(503, { detail: 'Cota excedida' }))
    const user = userEvent.setup()
    renderChat()

    await user.type(input(), 'Qual a pressão?{Enter}')
    expect(await screen.findByRole('alert')).toHaveTextContent('temporariamente indisponível')
    await user.click(screen.getByRole('button', { name: 'Tentar novamente' }))

    expect(await screen.findByText('10 bar')).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(within(log()).getAllByText('Qual a pressão?')).toHaveLength(1)
    expect(ask).toHaveBeenCalledTimes(2)
  })

  it('starts a new conversation', async () => {
    ask.mockRejectedValueOnce(new NetworkError())
    const user = userEvent.setup()
    renderChat()
    await user.type(input(), 'Qual a pressão?{Enter}')
    await screen.findByRole('alert')

    await user.click(screen.getByRole('button', { name: 'Nova conversa' }))

    expect(screen.getByText('Tire suas dúvidas sobre os manuais')).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})
