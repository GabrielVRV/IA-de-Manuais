import { useCallback, useEffect, useState } from 'react'

import { type AccessPolicy, canUseAssistant } from '@/features/assistants/domain/assistants'
import { useAssistantsGateway } from '@/features/assistants/presentation/assistants-gateway-context'
import { useCurrentUser } from '@/features/auth/presentation/session-context'
import { cx } from '@/shared/cx'
import { describeError } from '@/shared/http/describe-error'
import { randomPassword } from '@/shared/random-password'
import ui from '@/styles/ui.module.css'

import type { AssistantAccessChange, ManagedUser, UserRole } from '../domain/users'
import { UserAccessDialog } from './UserAccessDialog'
import { useUsersGateway } from './users-gateway-context'
import styles from './UsersAdmin.module.css'

const dateFormat = new Intl.DateTimeFormat('pt-BR', { dateStyle: 'short', timeStyle: 'short' })

/** Senha provisória a entregar ao usuário (mostrada uma única vez). */
interface Handover {
  readonly username: string
  readonly password: string
  readonly action: 'criado' | 'redefinida'
}

export function UsersAdmin() {
  const gateway = useUsersGateway()
  const assistants = useAssistantsGateway()
  const me = useCurrentUser()
  const [users, setUsers] = useState<ManagedUser[] | null>(null)
  const [policies, setPolicies] = useState<AccessPolicy[]>([])
  const [editingAccess, setEditingAccess] = useState<ManagedUser | null>(null)
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
    Promise.all([gateway.list(), assistants.policies()]).then(
      ([list, loaded]) => {
        if (!active) return
        setUsers(list)
        setPolicies(loaded)
      },
      (caught: unknown) => {
        if (active) setError(describeError(caught))
      },
    )
    return () => {
      active = false
    }
  }, [gateway, assistants])

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

  const resetPassword = (user: ManagedUser) => {
    if (!window.confirm(`Gerar uma nova senha provisória para ${user.displayName}?`)) return
    const password = randomPassword()
    void run(async () => {
      await gateway.resetPassword(user.id, password)
      setHandover({ username: user.username, password, action: 'redefinida' })
    })
  }

  const saveAccess = (user: ManagedUser, changes: readonly AssistantAccessChange[]) =>
    run(async () => {
      for (const change of changes) {
        await gateway.setAssistantAccess(user.id, change.assistantId, change.access)
      }
    })

  return (
    <div className={ui.page}>
      <header className={ui.pageHeader}>
        <h2 className={ui.pageTitle}>Usuários</h2>
        {users && (
          <span className={ui.muted}>{users.filter((u) => u.isActive).length} ativo(s)</span>
        )}
      </header>

      <div className={ui.stack}>
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
                  <th>Perfil</th>
                  {policies.length > 0 && <th>Acesso</th>}
                  <th>Situação</th>
                  <th>Último acesso</th>
                  <th>
                    <span className={ui.visuallyHidden}>Ações</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {users.map((user) => {
                  const isMe = user.id === me.id
                  return (
                    <tr key={user.id} className={cx(!user.isActive && styles.inactive)}>
                      <td className={styles.name}>
                        {user.displayName}
                        {isMe && <span className={ui.muted}> (você)</span>}
                      </td>
                      <td data-label="Login">
                        {user.username}
                        <span className={styles.subtle}>
                          {user.authSource === 'ad' ? 'Rede (AD)' : 'Local'}
                        </span>
                      </td>
                      <td data-label="Perfil">
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
                          <option value="user">Usuário</option>
                          <option value="admin">Administrador</option>
                        </select>
                      </td>
                      {policies.length > 0 && (
                        <td className={styles.accessCell} data-label="Acesso">
                          <div className={styles.access}>
                            <AccessSummary user={user} policies={policies} />
                            {user.role !== 'admin' && (
                              <button
                                type="button"
                                className={cx(ui.button, styles.manage)}
                                aria-label={`Gerenciar acessos de ${user.displayName}`}
                                onClick={() => {
                                  setEditingAccess(user)
                                }}
                              >
                                Gerenciar
                              </button>
                            )}
                          </div>
                        </td>
                      )}
                      <td data-label="Situação">
                        {!user.isActive ? (
                          <span className={ui.badge} data-tone="danger">
                            Inativo
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
                      <td className={cx(ui.muted, styles.nowrap)} data-label="Último acesso">
                        {user.lastLoginAt ? dateFormat.format(user.lastLoginAt) : 'Nunca'}
                      </td>
                      <td className={styles.actionsCell}>
                        <div className={styles.actions}>
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

      {editingAccess && (
        <UserAccessDialog
          user={editingAccess}
          policies={policies}
          onSave={(changes) => saveAccess(editingAccess, changes)}
          onClose={() => {
            setEditingAccess(null)
          }}
        />
      )}
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
        Usuários de rede (AD) não precisam ser criados: eles aparecem aqui no primeiro login e já
        usam os assistentes liberados para todos. Crie aqui só quem não tem usuário de rede.
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

/** Resumo do acesso a cada assistente, na tabela; a edição fica no diálogo. */
function AccessSummary({
  user,
  policies,
}: {
  readonly user: ManagedUser
  readonly policies: readonly AccessPolicy[]
}) {
  if (user.role === 'admin') {
    return <span className={ui.muted}>Todos (administrador)</span>
  }
  return (
    <ul className={styles.accessList}>
      {policies.map((policy) => {
        const access = user.assistantAccess[policy.assistantId]
        const allowed = canUseAssistant(policy, access)
        return (
          <li key={policy.assistantId}>
            <span className={ui.badge} data-tone={allowed ? 'success' : 'danger'}>
              {allowed ? 'Usa' : 'Sem acesso'}
            </span>{' '}
            {policy.name}
            {access && (
              <span className={styles.subtle}>
                {access === 'granted' ? 'Liberado para esta pessoa' : 'Bloqueado para esta pessoa'}
              </span>
            )}
          </li>
        )
      })}
    </ul>
  )
}
