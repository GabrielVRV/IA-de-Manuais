// Mesmas regras da API (domain/user.py no backend).
export const PASSWORD_MIN_LENGTH = 8
export const PASSWORD_MAX_LENGTH = 128

export type UserRole = 'admin' | 'user'

export interface SessionUser {
  readonly id: string
  readonly username: string
  readonly displayName: string
  readonly role: UserRole
  readonly mustChangePassword: boolean
}

export function isAdmin(user: SessionUser): boolean {
  return user.role === 'admin'
}

/** Porta: como a interface entra, sai e acompanha a sessão. */
export interface AuthGateway {
  /** Usuário da sessão atual, ou null se ninguém estiver logado. */
  currentUser(): Promise<SessionUser | null>
  login(username: string, password: string): Promise<SessionUser>
  logout(): Promise<void>
  changePassword(currentPassword: string, newPassword: string): Promise<void>
  /** Avisa quando a API recusar a sessão (expirada, encerrada). Retorna o cancelamento. */
  onSessionExpired(listener: () => void): () => void
}
