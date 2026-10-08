import type { UserRole } from '@/features/auth/domain/auth'

export type { UserRole }

export interface ManagedUser {
  readonly id: string
  readonly username: string
  readonly displayName: string
  readonly role: UserRole
  readonly isActive: boolean
  readonly mustChangePassword: boolean
  readonly lastLoginAt: Date | null
}

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
