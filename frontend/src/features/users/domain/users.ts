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
}

/** Usuário local. Os do TOTVS são cadastrados sozinhos no primeiro login. */
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
}
