import { useCallback, useEffect, useState } from 'react'

import { useCurrentUser } from '@/features/auth/presentation/session-context'
import { cx } from '@/shared/cx'
import { describeError } from '@/shared/http/describe-error'
import { randomPassword } from '@/shared/random-password'
import ui from '@/styles/ui.module.css'

import type { ManagedUser, UserRole } from '../domain/users'
import { useUsersGateway } from './users-gateway-context'
import styles from './UsersAdmin.module.css'

const dateFormat = new Intl.DateTimeFormat('pt-BR', { dateStyle: 'short', timeStyle: 'short' })

/** Quem aguarda liberação aparece primeiro; o resto mantém a ordem da API (por nome). */
function pendingFirst(users: readonly ManagedUser[]): ManagedUser[] {
  return [...users].sort((a, b) => Number(b.role === 'pending') - Number(a.role === 'pending'))
}

/** Senha provisória a entregar ao usuário (mostrada uma única vez). */
interface Handover {
  readonly username: string
  readonly password: string
  readonly action: 'criado' | 'redefinida'
}

export function UsersAdmin() {
  const gateway = useUsersGateway()
  const me = useCurrentUser()
  const [users, setUsers] = useState<ManagedUser[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [handover, setHandover] = useState<Handover | null>(null)

  const refresh = useCallback(async () => {
    try {
      setUsers(await gateway.list())
    } catch (caught) {
      setError(describeError(caught))
    }
  }, [gateway])

  // Carga inicial: o estado só muda nos callbacks da promessa, nunca no corpo do efeito.
  useEffect(() => {
    let active = true
    gateway.list().then(
      (list) => {
        if (active) setUsers(list)
      },
      (caught: unknown) => {
        if (active) setError(describeError(caught))
      },
    )
    return () => {
      active = false
    }
  }, [gateway])

  const run = async (action: () => Promise<unknown>) => {
    setError(null)
    try {
      await action()
      await refresh()
      return true
    } catch (caught) {
      setError(describeError(caught))
      return false
    }
  }

  const pendingCount = users?.filter((u) => u.isActive && u.role === 'pending').length ?? 0

  const resetPassword = (user: ManagedUser) => {
    if (!window.confirm(`Gerar uma nova senha provisória para ${user.displayName}?`)) return
    const password = randomPassword()
    void run(async () => {
      await gateway.resetPassword(user.id, password)
      setHandover({ username: user.username, password, action: 'redefinida' })
    })
  }

  return (
    <div className={ui.page}>
      <header className={ui.pageHeader}>
        <h2 className={ui.pageTitle}>Usuários</h2>
        {users && (
          <span className={ui.muted}>{users.filter((u) => u.isActive).length} ativo(s)</span>
        )}
      </header>

      <div className={ui.stack}>
        {pendingCount > 0 && (
          <p className={ui.alert} data-tone="warning" role="status">
            {pendingCount === 1
              ? '1 usuário do TOTVS aguarda liberação.'
              : `${String(pendingCount)} usuários do TOTVS aguardam liberação.`}{' '}
            Clique em <strong>Liberar</strong> ou escolha o perfil para dar acesso.
          </p>
        )}

        <CreateUserForm
          onCreate={async (user) =>
            run(async () => {
              await gateway.create(user)
              setHandover({
                username: user.username.trim().toLowerCase(),
                password: user.temporaryPassword,
                action: 'criado',
              })
            })
          }
        />

        {handover && (
          <div
            className={ui.alert}
            data-tone="success"
            role="status"
            aria-label="Senha provisória gerada"
          >
            {handover.action === 'criado' ? 'Usuário ' : 'Senha de '}
            <strong>{handover.username}</strong>{' '}
            {handover.action === 'criado' ? 'criado' : 'redefinida'}. Senha provisória:{' '}
            <span className={ui.code}>{handover.password}</span>
            <br />
            <span className={ui.hint}>
              Entregue ao usuário: ela não será mostrada de novo e precisará ser trocada no primeiro
              acesso.
            </span>
          </div>
        )}

        {error && (
          <p className={ui.alert} data-tone="danger" role="alert">
            {error}
          </p>
        )}

        {users === null && !error && <p className={ui.muted}>Carregando usuários…</p>}

        {users && (
          <div className={styles.tableWrapper}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>Nome</th>
                  <th>Login</th>
                  <th>Origem</th>
                  <th>Perfil</th>
                  <th>Situação</th>
                  <th>Último acesso</th>
                  <th>
                    <span className={ui.visuallyHidden}>Ações</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {pendingFirst(users).map((user) => {
                  const isMe = user.id === me.id
                  const pending = user.role === 'pending'
                  return (
                    <tr key={user.id} className={cx(!user.isActive && styles.inactive)}>
                      <td>
                        {user.displayName}
                        {isMe && <span className={ui.muted}> (você)</span>}
                      </td>
                      <td>{user.username}</td>
                      <td>{user.authSource === 'totvs' ? 'TOTVS' : 'Local'}</td>
                      <td>
                        <select
                          className={ui.select}
                          aria-label={`Perfil de ${user.displayName}`}
                          value={user.role}
                          disabled={isMe}
                          onChange={(event) => {
                            void run(() =>
                              gateway.update(user.id, { role: event.target.value as UserRole }),
                            )
                          }}
                        >
                          {pending && <option value="pending">Aguardando liberação</option>}
                          <option value="user">Usuário</option>
                          <option value="admin">Administrador</option>
                        </select>
                      </td>
                      <td>
                        {!user.isActive ? (
                          <span className={ui.badge} data-tone="danger">
                            Inativo
                          </span>
                        ) : pending ? (
                          <span className={ui.badge} data-tone="warning">
                            Aguardando liberação
                          </span>
                        ) : user.mustChangePassword ? (
                          <span className={ui.badge} data-tone="warning">
                            Aguardando 1º acesso
                          </span>
                        ) : (
                          <span className={ui.badge} data-tone="success">
                            Ativo
                          </span>
                        )}
                      </td>
                      <td className={ui.muted}>
                        {user.lastLoginAt ? dateFormat.format(user.lastLoginAt) : 'Nunca'}
                      </td>
                      <td>
                        <div className={styles.actions}>
                          {pending && user.isActive && (
                            <button
                              type="button"
                              className={cx(ui.button, ui.primary)}
                              onClick={() => {
                                void run(() => gateway.update(user.id, { role: 'user' }))
                              }}
                            >
                              Liberar
                            </button>
                          )}
                          {user.authSource === 'local' && (
                            <button
                              type="button"
                              className={ui.button}
                              onClick={() => {
                                resetPassword(user)
                              }}
                            >
                              Redefinir senha
                            </button>
                          )}
                          <button
                            type="button"
                            className={cx(ui.button, user.isActive && ui.danger)}
                            disabled={isMe}
                            onClick={() => {
                              void run(() => gateway.update(user.id, { isActive: !user.isActive }))
                            }}
                          >
                            {user.isActive ? 'Desativar' : 'Reativar'}
                          </button>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

function CreateUserForm({
  onCreate,
}: {
  readonly onCreate: (user: {
    username: string
    displayName: string
    role: UserRole
    temporaryPassword: string
  }) => Promise<boolean>
}) {
  const [username, setUsername] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [role, setRole] = useState<UserRole>('user')
  const [password, setPassword] = useState(() => randomPassword())
  const [submitting, setSubmitting] = useState(false)

  const submit = async () => {
    setSubmitting(true)
    const created = await onCreate({ username, displayName, role, temporaryPassword: password })
    setSubmitting(false)
    if (created) {
      setUsername('')
      setDisplayName('')
      setRole('user')
      setPassword(randomPassword())
    }
  }

  return (
    <form
      className={cx(ui.card, ui.stack)}
      onSubmit={(event) => {
        event.preventDefault()
        void submit()
      }}
    >
      <strong>Novo usuário local</strong>
      <span className={ui.hint}>
        Usuários do TOTVS não precisam ser criados: eles aparecem aqui no primeiro login, aguardando
        liberação. Crie aqui só quem não tem acesso ao TOTVS.
      </span>
      <div className={ui.row}>
        <label className={cx(ui.field, ui.grow)}>
          <span className={ui.label}>Nome</span>
          <input
            className={ui.input}
            value={displayName}
            onChange={(e) => {
              setDisplayName(e.target.value)
            }}
            required
          />
        </label>
        <label className={cx(ui.field, ui.grow)}>
          <span className={ui.label}>Login</span>
          <input
            className={ui.input}
            value={username}
            onChange={(e) => {
              setUsername(e.target.value)
            }}
            autoCapitalize="none"
            spellCheck={false}
            placeholder="maria.silva"
            required
          />
        </label>
        <label className={ui.field}>
          <span className={ui.label}>Perfil</span>
          <select
            className={ui.select}
            value={role}
            onChange={(e) => {
              setRole(e.target.value as UserRole)
            }}
          >
            <option value="user">Usuário</option>
            <option value="admin">Administrador</option>
          </select>
        </label>
      </div>
      <div className={ui.row}>
        <label className={cx(ui.field, ui.grow)}>
          <span className={ui.label}>Senha provisória</span>
          <input
            className={ui.input}
            value={password}
            onChange={(e) => {
              setPassword(e.target.value)
            }}
            required
          />
        </label>
        <button
          type="button"
          className={ui.button}
          onClick={() => {
            setPassword(randomPassword())
          }}
        >
          Gerar outra
        </button>
        <button type="submit" className={cx(ui.button, ui.primary)} disabled={submitting}>
          {submitting ? 'Criando…' : 'Criar usuário'}
        </button>
      </div>
      <span className={ui.hint}>
        Login: 3 a 50 caracteres (letras minúsculas, números, ponto, hífen ou sublinhado).
      </span>
    </form>
  )
}
