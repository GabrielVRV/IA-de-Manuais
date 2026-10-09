import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { PASSWORD_ALPHABET } from '@/shared/random-password'
import { ADMIN, fakeUsersGateway, managedUser, renderApp } from '@/test/fakes'

const me = managedUser({ id: ADMIN.id, username: 'admin', displayName: 'Ana Admin', role: 'admin' })
const joao = managedUser()
const pedro = managedUser({
  id: 'u-pedro',
  username: 'pedro',
  displayName: 'Pedro do TOTVS',
  role: 'pending',
  authSource: 'totvs',
})

function setup() {
  const users = fakeUsersGateway([me, joao, pedro])
  renderApp({ users, path: '/usuarios' })
  return { users, user: userEvent.setup() }
}

const row = (name: string) => screen.getByRole('row', { name: new RegExp(name) })

describe('<UsersAdmin />', () => {
  it('creates a user with a generated temporary password and shows it once', async () => {
    const { users, user } = setup()
    await screen.findByRole('table')
    const password = screen.getByLabelText<HTMLInputElement>('Senha provisória').value

    await user.type(screen.getByLabelText('Nome'), 'Maria Silva')
    await user.type(screen.getByLabelText('Login'), 'maria.silva')
    await user.click(screen.getByRole('button', { name: 'Criar usuário' }))

    expect(users.create).toHaveBeenCalledWith({
      username: 'maria.silva',
      displayName: 'Maria Silva',
      role: 'user',
      temporaryPassword: password,
    })
    const handover = await screen.findByRole('status', { name: 'Senha provisória gerada' })
    expect(handover).toHaveTextContent('maria.silva')
    expect(handover).toHaveTextContent(password)
    expect(row('Maria Silva')).toHaveTextContent('Aguardando 1º acesso')
    expect(password).toMatch(
      new RegExp(`^[${PASSWORD_ALPHABET}]{4}-[${PASSWORD_ALPHABET}]{4}-[${PASSWORD_ALPHABET}]{4}$`),
    )
  })

  it('shows the reason when creation is refused', async () => {
    const { user } = setup()
    await screen.findByRole('table')

    await user.type(screen.getByLabelText('Nome'), 'Outro João')
    await user.type(screen.getByLabelText('Login'), 'joao')
    await user.click(screen.getByRole('button', { name: 'Criar usuário' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      "Já existe um usuário com o login 'joao'",
    )
  })

  it('resets a password, deactivates and changes the role', async () => {
    const { users, user } = setup()
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    await screen.findByRole('table')

    await user.click(within(row('João')).getByRole('button', { name: 'Redefinir senha' }))
    expect(
      await screen.findByRole('status', { name: 'Senha provisória gerada' }),
    ).toHaveTextContent('Senha de joao redefinida')

    await user.click(within(row('João')).getByRole('button', { name: 'Desativar' }))
    expect(await within(row('João')).findByText('Inativo')).toBeInTheDocument()

    await user.selectOptions(within(row('João')).getByLabelText('Perfil de João'), 'admin')
    expect(users.update).toHaveBeenLastCalledWith('u-joao', { role: 'admin' })
  })

  it('does not let the administrator deactivate or demote themselves', async () => {
    setup()
    await screen.findByRole('table')

    expect(within(row('Ana Admin')).getByRole('button', { name: 'Desativar' })).toBeDisabled()
    expect(within(row('Ana Admin')).getByLabelText('Perfil de Ana Admin')).toBeDisabled()
  })

  it('highlights TOTVS users awaiting approval and releases them', async () => {
    const { users, user } = setup()
    await screen.findByRole('table')

    expect(screen.getByText(/1 usuário do TOTVS aguarda liberação/)).toBeInTheDocument()
    // Quem aguarda aparece no topo da tabela.
    expect(screen.getAllByRole('row')[1]).toHaveTextContent('Pedro do TOTVS')
    expect(row('Pedro')).toHaveTextContent('TOTVS')
    expect(within(row('Pedro')).queryByRole('button', { name: 'Redefinir senha' })).toBeNull()

    await user.click(within(row('Pedro')).getByRole('button', { name: 'Liberar' }))

    expect(users.update).toHaveBeenLastCalledWith('u-pedro', { role: 'user' })
    expect(await within(row('Pedro')).findByText('Ativo')).toBeInTheDocument()
    expect(screen.queryByText(/aguarda liberação/)).not.toBeInTheDocument()
  })
})
