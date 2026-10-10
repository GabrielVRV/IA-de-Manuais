import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router'
import { describe, expect, it } from 'vitest'

import { HttpError, NetworkError } from '@/shared/http/errors'
import { conversation, fakeQuestionGateway } from '@/test/fakes'

import type { Answer, ChatReply } from '../domain/chat'
import { ChatPage } from './ChatPage'
import { QuestionGatewayContext } from './question-gateway-context'

const notFound: Answer = { text: 'Não encontrei essa informação.', found: false, citations: [] }

function Location() {
  return <div data-testid="location">{useLocation().pathname}</div>
}

function renderChat({
  gateway = fakeQuestionGateway(),
  path = '/',
  userName = 'GABRIEL VIARO',
} = {}) {
  const page = <ChatPage userName={userName} />
  render(
    <QuestionGatewayContext value={gateway}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/" element={page}>
            <Route path="c/:conversationId" element={null} />
          </Route>
        </Routes>
        <Location />
      </MemoryRouter>
    </QuestionGatewayContext>,
  )
  return gateway
}

const input = () => screen.getByRole('textbox', { name: /sua pergunta/i })
const log = () => screen.getByRole('log')
const history = () => screen.getByRole('navigation', { name: 'Conversas anteriores' })
const location = () => screen.getByTestId('location')

describe('<ChatPage />', () => {
  it('greets by first name and suggests questions', () => {
    renderChat()

    expect(screen.getByRole('heading', { name: /Olá, Gabriel!/ })).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: /\?$/ })).toHaveLength(4)
  })

  it('answers with a link to the cited page and saves the new conversation', async () => {
    const user = userEvent.setup()
    const gateway = renderChat()

    await user.type(input(), 'Qual a pressão máxima?{Enter}')

    expect(within(log()).getByText('Qual a pressão máxima?')).toBeInTheDocument()
    expect(await screen.findByText('10 bar')).toContainHTML('<strong>10 bar</strong>')
    const source = screen.getByRole('link', { name: /Compressor CX-500/ })
    expect(source).toHaveAttribute('href', 'http://api/manuals/cx500/file#page=3')
    expect(source).toHaveAttribute('target', '_blank')
    expect(input()).toHaveValue('')
    expect(gateway.ask).toHaveBeenCalledWith(
      'Qual a pressão máxima?',
      null,
      expect.any(AbortSignal),
    )
    // A conversa vira uma URL própria e entra no topo do histórico, sem recarregar.
    await waitFor(() => {
      expect(location()).toHaveTextContent('/c/nova-1')
    })
    expect(within(history()).getByRole('link', { name: 'Qual a pressão máxima?' })).toHaveAttribute(
      'aria-current',
      'page',
    )
    expect(gateway.getConversation).not.toHaveBeenCalled()
  })

  it('sends follow-ups in the same conversation', async () => {
    const user = userEvent.setup()
    const gateway = renderChat()

    await user.type(input(), 'Qual a pressão máxima?{Enter}')
    await screen.findByText('10 bar')
    await user.type(input(), 'E a mínima?{Enter}')

    await screen.findAllByText('10 bar').then((found) => {
      expect(found).toHaveLength(2)
    })
    expect(gateway.ask).toHaveBeenLastCalledWith('E a mínima?', 'nova-1', expect.any(AbortSignal))
  })

  it('shows progress while waiting and lets the user stop', async () => {
    const gateway = fakeQuestionGateway()
    gateway.ask.mockReturnValueOnce(new Promise<ChatReply>(() => undefined))
    const user = userEvent.setup()
    renderChat({ gateway })

    await user.type(input(), 'Qual a pressão?{Enter}')

    expect(screen.getByText('Consultando os manuais…')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Parar resposta' }))

    expect(screen.queryByText('Consultando os manuais…')).not.toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('Você interrompeu a resposta.')
    expect(screen.getByRole('button', { name: 'Perguntar' })).toBeInTheDocument()
  })

  it('uses Shift+Enter for a new line instead of sending', async () => {
    const user = userEvent.setup()
    const gateway = renderChat()

    await user.type(input(), 'Linha um{Shift>}{Enter}{/Shift}linha dois')

    expect(input()).toHaveValue('Linha um\nlinha dois')
    expect(gateway.ask).not.toHaveBeenCalled()
  })

  it('does not send questions that are too short', async () => {
    const user = userEvent.setup()
    const gateway = renderChat()

    await user.type(input(), 'oi{Enter}')

    expect(screen.getByRole('button', { name: 'Perguntar' })).toBeDisabled()
    expect(gateway.ask).not.toHaveBeenCalled()
  })

  it('asks a suggested question with one click', async () => {
    const user = userEvent.setup()
    const gateway = renderChat()

    await user.click(screen.getByRole('button', { name: /manutenção preventiva/ }))

    expect(gateway.ask).toHaveBeenCalledWith(
      'Como faço a manutenção preventiva do motorredutor?',
      null,
      expect.any(AbortSignal),
    )
  })

  it('marks answers that were not found in the manuals', async () => {
    const gateway = fakeQuestionGateway()
    gateway.state.answer = notFound
    const user = userEvent.setup()
    renderChat({ gateway })

    await user.type(input(), 'Como faço um bolo?{Enter}')

    const answer = (await screen.findByText('Não encontrei essa informação.')).closest('article')
    expect(answer).toHaveAttribute('data-found', 'false')
    expect(screen.getByText('Não consta nos manuais')).toBeInTheDocument()
    expect(screen.queryByText('Fontes')).not.toBeInTheDocument()
  })

  it('explains failures and retries without repeating the question', async () => {
    const gateway = fakeQuestionGateway()
    gateway.ask.mockRejectedValueOnce(new HttpError(503, { detail: 'Cota excedida' }))
    const user = userEvent.setup()
    renderChat({ gateway })

    await user.type(input(), 'Qual a pressão?{Enter}')
    expect(await screen.findByRole('alert')).toHaveTextContent('temporariamente indisponível')
    await user.click(screen.getByRole('button', { name: 'Tentar novamente' }))

    expect(await screen.findByText('10 bar')).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(within(log()).getAllByText('Qual a pressão?')).toHaveLength(1)
    expect(gateway.ask).toHaveBeenCalledTimes(2)
  })

  it('opens a conversation from the history', async () => {
    const user = userEvent.setup()
    const gateway = renderChat({
      gateway: fakeQuestionGateway([
        conversation(),
        conversation({ id: 'c2', title: 'Troca de óleo', exchanges: [] }),
      ]),
    })

    await user.click(await within(history()).findByRole('link', { name: 'Pressão do compressor' }))

    expect(await within(log()).findByText('Qual a pressão do compressor?')).toBeInTheDocument()
    expect(within(log()).getByText('10 bar')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Pressão do compressor' })).toBeInTheDocument()
    expect(gateway.getConversation).toHaveBeenCalledWith('c1', expect.any(AbortSignal))
  })

  it('filters the history ignoring accents', async () => {
    const user = userEvent.setup()
    renderChat({
      gateway: fakeQuestionGateway([
        conversation(),
        conversation({ id: 'c2', title: 'Troca de óleo' }),
      ]),
    })
    await within(history()).findByText('Pressão do compressor')

    await user.type(screen.getByRole('searchbox', { name: 'Buscar no histórico' }), 'oleo')

    expect(within(history()).getByText('Troca de óleo')).toBeInTheDocument()
    expect(within(history()).queryByText('Pressão do compressor')).not.toBeInTheDocument()
  })

  it('renames a conversation', async () => {
    const user = userEvent.setup()
    const gateway = renderChat({ gateway: fakeQuestionGateway([conversation()]) })

    await user.click(
      await within(history()).findByRole('button', { name: 'Renomear “Pressão do compressor”' }),
    )
    const field = screen.getByRole('textbox', { name: 'Novo título da conversa' })
    await user.clear(field)
    await user.type(field, 'Pressão do CX-500{Enter}')

    expect(await within(history()).findByText('Pressão do CX-500')).toBeInTheDocument()
    expect(gateway.renameConversation).toHaveBeenCalledWith('c1', 'Pressão do CX-500')
  })

  it('deletes the open conversation after confirming and starts a new one', async () => {
    const user = userEvent.setup()
    const gateway = renderChat({ gateway: fakeQuestionGateway([conversation()]), path: '/c/c1' })
    await within(log()).findByText('Qual a pressão do compressor?')

    await user.click(
      within(history()).getByRole('button', { name: 'Apagar “Pressão do compressor”' }),
    )
    await user.click(within(history()).getByRole('button', { name: 'Apagar' }))

    expect(await screen.findByRole('heading', { name: /Olá, Gabriel!/ })).toBeInTheDocument()
    expect(location()).toHaveTextContent(/^\/$/)
    expect(gateway.deleteConversation).toHaveBeenCalledWith('c1')
    expect(within(history()).queryByText('Pressão do compressor')).not.toBeInTheDocument()
  })

  it('explains when an opened conversation no longer exists', async () => {
    renderChat({ path: '/c/sumiu' })

    expect(await screen.findByRole('alert')).toHaveTextContent('não existe mais')
    expect(screen.getByRole('link', { name: 'Começar uma nova conversa' })).toBeInTheDocument()
  })

  it('reports connection failures when loading the history', async () => {
    const gateway = fakeQuestionGateway()
    gateway.listConversations.mockRejectedValueOnce(new NetworkError())
    renderChat({ gateway })

    expect(await within(history()).findByText(/conectar ao servidor/)).toBeInTheDocument()
  })
})
