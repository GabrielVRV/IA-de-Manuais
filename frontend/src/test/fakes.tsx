/** Gateways falsos e montagem da aplicação para testes de interface. */
import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { vi } from 'vitest'

import { App } from '@/app/App'
import type { AuthGateway, SessionUser } from '@/features/auth/domain/auth'
import { AuthGatewayContext } from '@/features/auth/presentation/session-context'
import { SessionProvider } from '@/features/auth/presentation/SessionProvider'
import type {
  Answer,
  Conversation,
  ConversationSummary,
  QuestionGateway,
} from '@/features/chat/domain/chat'
import { QuestionGatewayContext } from '@/features/chat/presentation/question-gateway-context'
import type { HealthGateway } from '@/features/health/domain/api-health'
import { HealthGatewayContext } from '@/features/health/presentation/health-gateway-context'
import type { ManualsGateway, ManualSummary } from '@/features/manuals/domain/manuals'
import { ManualsGatewayContext } from '@/features/manuals/presentation/manuals-gateway-context'
import type { ManagedUser, UserRole, UsersGateway } from '@/features/users/domain/users'
import { UsersGatewayContext } from '@/features/users/presentation/users-gateway-context'
import { HttpError } from '@/shared/http/errors'

export const ADMIN: SessionUser = {
  id: 'u-admin',
  username: 'admin',
  displayName: 'Ana Admin',
  role: 'admin',
  authSource: 'local',
  mustChangePassword: false,
}

export const REGULAR: SessionUser = {
  ...ADMIN,
  id: 'u-joao',
  username: 'joao',
  displayName: 'João',
  role: 'user',
}

/** Primeiro login pelo TOTVS: ainda aguarda um administrador liberar o acesso. */
export const PENDING: SessionUser = {
  ...REGULAR,
  id: 'u-pedro',
  username: 'pedro',
  displayName: 'Pedro do TOTVS',
  role: 'pending',
  authSource: 'totvs',
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
    authSource: 'local',
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
    create: vi.fn((user: { username: string; displayName: string; role: UserRole }) => {
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
    update: vi.fn(
      (id: string, changes: { isActive?: boolean; role?: 'admin' | 'user' | 'pending' }) =>
        replace(id, changes),
    ),
  } satisfies UsersGateway & { state: typeof state }
}

export const ANSWER: Answer = {
  text: 'A pressão máxima é **10 bar**.',
  found: true,
  citations: [
    { manualId: 'cx500', manualTitle: 'Compressor CX-500', pages: [3, 4], pagesLabel: 'p. 3-4' },
  ],
}

export function conversation(overrides: Partial<Conversation> = {}): Conversation {
  return {
    id: 'c1',
    title: 'Pressão do compressor',
    createdAt: new Date('2026-10-07T10:00:00Z'),
    updatedAt: new Date('2026-10-07T10:05:00Z'),
    exchanges: [
      {
        question: 'Qual a pressão do compressor?',
        answer: ANSWER,
        askedAt: new Date('2026-10-07T10:00:00Z'),
      },
    ],
    ...overrides,
  }
}

/** Servidor de conversas em memória: cada pergunta respondida vai para o histórico. */
export function fakeQuestionGateway(initial: Conversation[] = []) {
  const state = { conversations: [...initial], answer: ANSWER, created: 0 }
  const summary = (c: Conversation): ConversationSummary => ({
    id: c.id,
    title: c.title,
    createdAt: c.createdAt,
    updatedAt: c.updatedAt,
    exchangeCount: c.exchanges.length,
  })
  const find = (id: string) => {
    const found = state.conversations.find((c) => c.id === id)
    if (!found) throw new HttpError(404, { detail: 'Conversa não encontrada' })
    return found
  }
  const gateway = {
    state,
    ask: vi.fn((question: string, conversationId: string | null) => {
      const now = new Date()
      const exchange = { question, answer: state.answer, askedAt: now }
      let current: Conversation
      if (conversationId) {
        const existing = find(conversationId)
        current = { ...existing, updatedAt: now, exchanges: [...existing.exchanges, exchange] }
        state.conversations = state.conversations.map((c) => (c.id === current.id ? current : c))
      } else {
        state.created += 1
        current = {
          id: `nova-${String(state.created)}`,
          title: question,
          createdAt: now,
          updatedAt: now,
          exchanges: [exchange],
        }
        state.conversations = [current, ...state.conversations]
      }
      return Promise.resolve({
        answer: state.answer,
        conversation: { id: current.id, title: current.title },
      })
    }),
    listConversations: vi.fn(() => Promise.resolve(state.conversations.map(summary))),
    // Dentro do then: o 404 de find() vira uma promessa rejeitada, como na API.
    getConversation: vi.fn((id: string) => Promise.resolve().then(() => find(id))),
    renameConversation: vi.fn((id: string, title: string) => {
      state.conversations = state.conversations.map((c) => (c.id === id ? { ...c, title } : c))
      return Promise.resolve({ id, title })
    }),
    deleteConversation: vi.fn((id: string) => {
      state.conversations = state.conversations.filter((c) => c.id !== id)
      return Promise.resolve()
    }),
    sourceUrl: (citation: { manualId: string; pages: readonly number[] }) =>
      `http://api/manuals/${citation.manualId}/file#page=${String(citation.pages[0])}`,
  } satisfies QuestionGateway & { state: typeof state }
  return gateway
}

interface RenderAppOptions {
  readonly auth?: FakeAuthGateway
  readonly manuals?: ManualsGateway
  readonly users?: UsersGateway
  readonly questions?: QuestionGateway
  readonly path?: string
}

export function renderApp(options: RenderAppOptions = {}) {
  const auth = options.auth ?? new FakeAuthGateway()
  const health: HealthGateway = {
    check: () => Promise.resolve({ status: 'up', version: '0.1.0', components: {} }),
  }
  const questions = options.questions ?? fakeQuestionGateway()
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
