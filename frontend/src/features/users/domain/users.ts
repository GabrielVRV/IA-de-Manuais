import type { AssistantId, UserAccess } from '@/features/assistants/domain/assistants'
import type { AuthSource, UserRole } from '@/features/auth/domain/auth'

export type { AuthSource, UserRole }

export interface ManagedUser {
  readonly id: string
  readonly username: string
  readonly displayName: string
  readonly role: UserRole
  readonly authSource: AuthSource
  readonly isActive: boolean
  readonly mustChangePassword: boolean
  readonly lastLoginAt: Date | null
  /** Exceções ao acesso padrão; assistente ausente = segue o padrão. */
  readonly assistantAccess: Partial<Record<AssistantId, UserAccess>>
}

/** Exceção a gravar: ``null`` = o usuário volta a seguir o padrão do assistente. */
export interface AssistantAccessChange {
  readonly assistantId: AssistantId
  readonly access: UserAccess | null
}

/** Usuário local. Os do AD são cadastrados sozinhos no primeiro login. */
export interface NewUser {
  readonly username: string
  readonly displayName: string
  readonly role: UserRole
  readonly temporaryPassword: string
}

/** Porta: administração de usuários, independente de transporte. */
export interface UsersGateway {
  list(): Promise<ManagedUser[]>
  create(user: NewUser): Promise<ManagedUser>
  resetPassword(id: string, temporaryPassword: string): Promise<ManagedUser>
  update(id: string, changes: { isActive?: boolean; role?: UserRole }): Promise<ManagedUser>
  /** Libera ou bloqueia um assistente para o usuário; null = volta ao padrão. */
  setAssistantAccess(id: string, assistantId: AssistantId, access: UserAccess | null): Promise<void>
}
