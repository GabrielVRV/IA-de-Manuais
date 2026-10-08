/** Gateways falsos e montagem da aplicação para testes de interface. */
import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { vi } from 'vitest'

import { App } from '@/app/App'
import type { AuthGateway, SessionUser } from '@/features/auth/domain/auth'
import { AuthGatewayContext } from '@/features/auth/presentation/session-context'
import { SessionProvider } from '@/features/auth/presentation/SessionProvider'
import type { QuestionGateway } from '@/features/chat/domain/chat'
import { QuestionGatewayContext } from '@/features/chat/presentation/question-gateway-context'
import type { HealthGateway } from '@/features/health/domain/api-health'
import { HealthGatewayContext } from '@/features/health/presentation/health-gateway-context'
import type { ManualsGateway, ManualSummary } from '@/features/manuals/domain/manuals'
import { ManualsGatewayContext } from '@/features/manuals/presentation/manuals-gateway-context'
import type { ManagedUser, UsersGateway } from '@/features/users/domain/users'
import { UsersGatewayContext } from '@/features/users/presentation/users-gateway-context'
import { HttpError } from '@/shared/http/errors'

export const ADMIN: SessionUser = {
  id: 'u-admin',
  username: 'admin',
  displayName: 'Ana Admin',
  role: 'admin',
  mustChangePassword: false,
}

export const REGULAR: SessionUser = {
  ...ADMIN,
  id: 'u-joao',
  username: 'joao',
  displayName: 'João',
  role: 'user',
}

export class FakeAuthGateway implements AuthGateway {
  user: SessionUser | null
  password = 'senha-correta'
  #listeners = new Set<() => void>()

  constructor(user: SessionUser | null = ADMIN) {
    this.user = user
  }

  currentUser = vi.fn(() => Promise.resolve(this.user))

  login = vi.fn((username: string, password: string) => {
    if (password !== this.password) {
      return Promise.reject(new HttpError(401, { detail: 'Usuário ou senha inválidos' }))
    }
    this.user = { ...(this.user ?? ADMIN), username }
    return Promise.resolve(this.user)
  })

  logout = vi.fn(() => {
    this.user = null
    return Promise.resolve()
  })

  changePassword = vi.fn((current: string) =>
    current === this.password
      ? Promise.resolve()
      : Promise.reject(new HttpError(422, { detail: 'A senha atual está incorreta' })),
  )

  onSessionExpired(listener: () => void): () => void {
    this.#listeners.add(listener)
    return () => this.#listeners.delete(listener)
  }

  expireSession(): void {
    for (const listener of this.#listeners) listener()
  }
}

export function manual(overrides: Partial<ManualSummary> = {}): ManualSummary {
  return {
    id: 'm1',
    title: 'Compressor CX-500',
    fileName: 'cx500.pdf',
    status: 'indexed',
    pageCount: 7,
    chunkCount: 12,
    failureReason: null,
    createdAt: new Date('2026-10-07T10:00:00Z'),
    ...overrides,
  }
}

export function fakeManualsGateway(initial: ManualSummary[] = [manual()]) {
  const state = { manuals: [...initial] }
  const gateway = {
    state,
    list: vi.fn(() => Promise.resolve([...state.manuals])),
    upload: vi.fn((file: File) => {
      const created = manual({
        id: file.name,
        title: file.name,
        fileName: file.name,
        status: 'processing',
      })
      state.manuals = [created, ...state.manuals]
      return Promise.resolve(created)
    }),
    reindex: vi.fn((id: string) => Promise.resolve(manual({ id, status: 'processing' }))),
    remove: vi.fn((id: string) => {
      state.manuals = state.manuals.filter((m) => m.id !== id)
      return Promise.resolve()
    }),
    fileUrl: (id: string) => `http://api/manuals/${id}/file`,
  } satisfies ManualsGateway & { state: typeof state }
  return gateway
}

export function managedUser(overrides: Partial<ManagedUser> = {}): ManagedUser {
  return {
    id: 'u-joao',
    username: 'joao',
    displayName: 'João',
    role: 'user',
    isActive: true,
    mustChangePassword: false,
    lastLoginAt: null,
    ...overrides,
  }
}

export function fakeUsersGateway(initial: ManagedUser[]) {
  const state = { users: [...initial] }
  const replace = (id: string, changes: Partial<ManagedUser>) => {
    state.users = state.users.map((u) => (u.id === id ? { ...u, ...changes } : u))
    return Promise.resolve(state.users.find((u) => u.id === id) ?? managedUser())
  }
  return {
    state,
    list: vi.fn(() => Promise.resolve([...state.users])),
    create: vi.fn((user: { username: string; displayName: string; role: 'admin' | 'user' }) => {
      if (state.users.some((u) => u.username === user.username)) {
        return Promise.reject(
          new HttpError(409, { detail: `Já existe um usuário com o login '${user.username}'` }),
        )
      }
      const created = managedUser({ id: `u-${user.username}`, ...user, mustChangePassword: true })
      state.users = [...state.users, created]
      return Promise.resolve(created)
    }),
    resetPassword: vi.fn((id: string) => replace(id, { mustChangePassword: true })),
    update: vi.fn((id: string, changes: { isActive?: boolean; role?: 'admin' | 'user' }) =>
      replace(id, changes),
    ),
  } satisfies UsersGateway & { state: typeof state }
}

interface RenderAppOptions {
  readonly auth?: FakeAuthGateway
  readonly manuals?: ManualsGateway
  readonly users?: UsersGateway
  readonly path?: string
}

export function renderApp(options: RenderAppOptions = {}) {
  const auth = options.auth ?? new FakeAuthGateway()
  const health: HealthGateway = {
    check: () => Promise.resolve({ status: 'up', version: '0.1.0', components: {} }),
  }
  const questions: QuestionGateway = {
    ask: () => Promise.resolve({ text: 'ok', found: true, citations: [] }),
    sourceUrl: () => '#',
  }
  const view = render(
    <AuthGatewayContext value={auth}>
      <HealthGatewayContext value={health}>
        <QuestionGatewayContext value={questions}>
          <ManualsGatewayContext value={options.manuals ?? fakeManualsGateway()}>
            <UsersGatewayContext value={options.users ?? fakeUsersGateway([])}>
              <SessionProvider>
                <MemoryRouter initialEntries={[options.path ?? '/']}>
                  <App />
                </MemoryRouter>
              </SessionProvider>
            </UsersGatewayContext>
          </ManualsGatewayContext>
        </QuestionGatewayContext>
      </HealthGatewayContext>
    </AuthGatewayContext>,
  )
  return { ...view, auth }
}
