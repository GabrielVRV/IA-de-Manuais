import { act, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { ADMIN, FakeAuthGateway, PENDING, REGULAR, renderApp } from '@/test/fakes'

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

    it('keeps AD users awaiting approval out until an administrator releases them', async () => {
      const user = userEvent.setup()
      const auth = new FakeAuthGateway(PENDING)
      renderApp({ auth })

      expect(
        await screen.findByRole('heading', { name: 'Aguardando liberação' }),
      ).toBeInTheDocument()
      expect(screen.getByText('Pedro da Rede')).toBeInTheDocument()
      expect(screen.queryByRole('textbox', { name: /sua pergunta/i })).not.toBeInTheDocument()

      await user.click(screen.getByRole('button', { name: 'Verificar novamente' }))
      expect(await screen.findByRole('status')).toHaveTextContent('ainda não foi liberado')

      auth.user = { ...PENDING, role: 'user' }
      await user.click(screen.getByRole('button', { name: 'Verificar novamente' }))
      expect(await screen.findByRole('textbox', { name: /sua pergunta/i })).toBeInTheDocument()
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

    it('switches between light, dark and system theme and remembers the choice', async () => {
      const user = userEvent.setup()
      renderApp()
      const theme = await screen.findByRole('group', { name: 'Tema' })
      expect(within(theme).getByRole('button', { name: 'Tema do sistema' })).toHaveAttribute(
        'aria-pressed',
        'true',
      )

      await user.click(within(theme).getByRole('button', { name: 'Tema escuro' }))

      expect(document.documentElement.dataset.theme).toBe('dark')
      expect(localStorage.getItem('ma-theme')).toBe('dark')
      expect(within(theme).getByRole('button', { name: 'Tema escuro' })).toHaveAttribute(
        'aria-pressed',
        'true',
      )

      await user.click(within(theme).getByRole('button', { name: 'Tema do sistema' }))

      expect(document.documentElement.dataset.theme).toBeUndefined()
      expect(localStorage.getItem('ma-theme')).toBeNull()
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
    it('gives administrators one entry to the administration area', async () => {
      const user = userEvent.setup()
      renderApp({ auth: new FakeAuthGateway(ADMIN) })

      await user.click(
        await within(
          await screen.findByRole('navigation', { name: 'Navegação principal' }),
        ).findByRole('link', { name: 'Administração' }),
      )

      expect(within(nav()).queryByRole('link', { name: 'Manuais' })).not.toBeInTheDocument()
      const admin = screen.getByRole('navigation', { name: 'Administração' })
      expect(within(admin).getByRole('heading', { name: 'Geral' })).toBeInTheDocument()
      expect(
        within(admin).getByRole('heading', { name: 'Assistente de Engenharia' }),
      ).toBeInTheDocument()
      // A área abre em Usuários.
      expect(await screen.findByRole('heading', { name: 'Usuários', level: 2 })).toBeInTheDocument()
      expect(within(admin).getByRole('link', { name: 'Usuários' })).toHaveAttribute(
        'aria-current',
        'page',
      )
      expect(within(nav()).getByRole('link', { name: 'Administração' })).toHaveClass(/active/)

      await user.click(within(admin).getByRole('link', { name: 'Manuais' }))

      expect(await screen.findByRole('heading', { name: 'Manuais', level: 2 })).toBeInTheDocument()
    })

    it('sends old bookmarks to the new administration addresses', async () => {
      renderApp({ auth: new FakeAuthGateway(ADMIN), path: '/consumo' })

      expect(await screen.findByRole('heading', { name: 'Consumo', level: 2 })).toBeInTheDocument()
      expect(
        within(screen.getByRole('navigation', { name: 'Administração' })).getByRole('link', {
          name: 'Consumo',
        }),
      ).toHaveAttribute('aria-current', 'page')
    })

    it('hides the administration from regular users and sends direct visits back to the chat', async () => {
      renderApp({ auth: new FakeAuthGateway(REGULAR), path: '/admin/manuais' })

      expect(await screen.findByRole('textbox', { name: /sua pergunta/i })).toBeInTheDocument()
      expect(within(nav()).queryByRole('link', { name: 'Administração' })).not.toBeInTheDocument()
    })

    it('lets local users change their own password', async () => {
      const user = userEvent.setup()
      renderApp({ auth: new FakeAuthGateway(REGULAR) })

      await user.click(await screen.findByRole('link', { name: 'João' }))

      expect(screen.getByRole('heading', { name: 'Trocar minha senha' })).toBeInTheDocument()
    })

    it('does not offer a password change to AD users', async () => {
      renderApp({ auth: new FakeAuthGateway({ ...REGULAR, authSource: 'ad' }), path: '/senha' })

      expect(await screen.findByRole('textbox', { name: /sua pergunta/i })).toBeInTheDocument()
      expect(screen.getByText('João')).not.toHaveAttribute('href')
    })
  })
})
