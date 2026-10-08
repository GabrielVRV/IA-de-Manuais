import { act, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { ADMIN, FakeAuthGateway, REGULAR, renderApp } from '@/test/fakes'

const nav = () => screen.getByRole('navigation', { name: 'Navegação principal' })

describe('<App />', () => {
  describe('login', () => {
    it('asks anonymous visitors to log in and then opens the chat', async () => {
      const user = userEvent.setup()
      const auth = new FakeAuthGateway(null)
      renderApp({ auth })

      await user.type(await screen.findByLabelText('Usuário'), 'Ana')
      await user.type(screen.getByLabelText('Senha'), 'senha-correta')
      await user.click(screen.getByRole('button', { name: 'Entrar' }))

      expect(await screen.findByRole('textbox', { name: /sua pergunta/i })).toBeInTheDocument()
      expect(auth.login).toHaveBeenCalledWith('Ana', 'senha-correta')
    })

    it('explains a refused login and clears the password', async () => {
      const user = userEvent.setup()
      renderApp({ auth: new FakeAuthGateway(null) })

      await user.type(await screen.findByLabelText('Usuário'), 'ana')
      await user.type(screen.getByLabelText('Senha'), 'errada')
      await user.click(screen.getByRole('button', { name: 'Entrar' }))

      expect(await screen.findByRole('alert')).toHaveTextContent('Usuário ou senha inválidos')
      expect(screen.getByLabelText('Senha')).toHaveValue('')
    })

    it('requires a new password after a temporary one', async () => {
      const user = userEvent.setup()
      const auth = new FakeAuthGateway({ ...REGULAR, mustChangePassword: true })
      renderApp({ auth })

      expect(await screen.findByRole('heading', { name: 'Crie sua senha' })).toBeInTheDocument()
      await user.type(screen.getByLabelText('Senha atual'), 'senha-correta')
      await user.type(screen.getByLabelText('Nova senha'), 'minha-senha-nova')
      await user.type(screen.getByLabelText('Confirme a nova senha'), 'minha-senha-nova')
      await user.click(screen.getByRole('button', { name: 'Trocar senha' }))

      expect(await screen.findByRole('textbox', { name: /sua pergunta/i })).toBeInTheDocument()
      expect(auth.changePassword).toHaveBeenCalledWith('senha-correta', 'minha-senha-nova')
    })

    it('validates the new password before sending it', async () => {
      const user = userEvent.setup()
      const auth = new FakeAuthGateway({ ...REGULAR, mustChangePassword: true })
      renderApp({ auth })

      await user.type(await screen.findByLabelText('Senha atual'), 'senha-correta')
      await user.type(screen.getByLabelText('Nova senha'), 'minha-senha-nova')
      await user.type(screen.getByLabelText('Confirme a nova senha'), 'outra-coisa-1')
      await user.click(screen.getByRole('button', { name: 'Trocar senha' }))

      expect(screen.getByRole('alert')).toHaveTextContent('não confere')
      expect(auth.changePassword).not.toHaveBeenCalled()
    })

    it('returns to the login screen with a notice when the session expires', async () => {
      const auth = new FakeAuthGateway(ADMIN)
      renderApp({ auth })
      await screen.findByRole('textbox', { name: /sua pergunta/i })

      act(() => {
        auth.expireSession()
      })

      expect(await screen.findByRole('button', { name: 'Entrar' })).toBeInTheDocument()
      expect(screen.getByRole('status')).toHaveTextContent('Sua sessão expirou')
    })

    it('logs out', async () => {
      const user = userEvent.setup()
      const { auth } = renderApp()

      await user.click(await screen.findByRole('button', { name: 'Sair' }))

      expect(await screen.findByRole('button', { name: 'Entrar' })).toBeInTheDocument()
      expect(auth.logout).toHaveBeenCalledOnce()
    })
  })

  describe('navigation', () => {
    it('shows the administration pages only to administrators', async () => {
      renderApp({ auth: new FakeAuthGateway(ADMIN) })

      expect(
        await within(await screen.findByRole('navigation')).findByRole('link', { name: 'Manuais' }),
      ).toBeInTheDocument()
      expect(within(nav()).getByRole('link', { name: 'Usuários' })).toBeInTheDocument()
      expect(screen.getByText('Ana Admin')).toBeInTheDocument()
    })

    it('hides them from regular users and sends direct visits back to the chat', async () => {
      renderApp({ auth: new FakeAuthGateway(REGULAR), path: '/manuais' })

      expect(await screen.findByRole('textbox', { name: /sua pergunta/i })).toBeInTheDocument()
      expect(within(nav()).queryByRole('link', { name: 'Manuais' })).not.toBeInTheDocument()
    })

    it('lets anyone change their own password', async () => {
      const user = userEvent.setup()
      renderApp({ auth: new FakeAuthGateway(REGULAR) })

      await user.click(await screen.findByRole('link', { name: 'João' }))

      expect(screen.getByRole('heading', { name: 'Trocar minha senha' })).toBeInTheDocument()
    })
  })
})
