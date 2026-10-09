// Mesmas regras da API (domain/user.py no backend).
export const PASSWORD_MIN_LENGTH = 8
export const PASSWORD_MAX_LENGTH = 128

/** 'pending': entrou pelo TOTVS e aguarda um administrador liberar o acesso. */
export type UserRole = 'admin' | 'user' | 'pending'

/** Quem confere a senha: este sistema ('local') ou o TOTVS. */
export type AuthSource = 'local' | 'totvs'

export interface SessionUser {
  readonly id: string
  readonly username: string
  readonly displayName: string
  readonly role: UserRole
  readonly authSource: AuthSource
  readonly mustChangePassword: boolean
}

export function isAdmin(user: SessionUser): boolean {
  return user.role === 'admin'
}

export function isPending(user: SessionUser): boolean {
  return user.role === 'pending'
}

/** Só usuários locais trocam a senha aqui; os do TOTVS trocam no próprio TOTVS. */
export function managesPasswordHere(user: SessionUser): boolean {
  return user.authSource === 'local'
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
