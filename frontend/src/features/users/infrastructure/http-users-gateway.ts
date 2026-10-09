import { z } from 'zod'

import { InvalidResponseError } from '@/shared/http/errors'
import type { HttpClient } from '@/shared/http/http-client'

import type { ManagedUser, NewUser, UserRole, UsersGateway } from '../domain/users'

const userSchema = z.object({
  id: z.string(),
  username: z.string(),
  display_name: z.string(),
  role: z.enum(['admin', 'user', 'pending']),
  auth_source: z.enum(['local', 'totvs']),
  is_active: z.boolean(),
  must_change_password: z.boolean(),
  last_login_at: z.iso.datetime({ offset: true }).nullable(),
})

function toUser(body: unknown): ManagedUser {
  const result = userSchema.safeParse(body)
  if (!result.success) throw new InvalidResponseError({ cause: result.error })
  const u = result.data
  return {
    id: u.id,
    username: u.username,
    displayName: u.display_name,
    role: u.role,
    authSource: u.auth_source,
    isActive: u.is_active,
    mustChangePassword: u.must_change_password,
    lastLoginAt: u.last_login_at ? new Date(u.last_login_at) : null,
  }
}

export class HttpUsersGateway implements UsersGateway {
  readonly #http: HttpClient

  constructor(http: HttpClient) {
    this.#http = http
  }

  async list(): Promise<ManagedUser[]> {
    const body = await this.#http.getJson('/api/v1/users')
    if (!Array.isArray(body)) throw new InvalidResponseError()
    return body.map(toUser)
  }

  async create(user: NewUser): Promise<ManagedUser> {
    return toUser(
      await this.#http.postJson('/api/v1/users', {
        username: user.username,
        display_name: user.displayName,
        role: user.role,
        temporary_password: user.temporaryPassword,
      }),
    )
  }

  async resetPassword(id: string, temporaryPassword: string): Promise<ManagedUser> {
    return toUser(
      await this.#http.postJson(`/api/v1/users/${encodeURIComponent(id)}/reset-password`, {
        temporary_password: temporaryPassword,
      }),
    )
  }

  async update(id: string, changes: { isActive?: boolean; role?: UserRole }): Promise<ManagedUser> {
    return toUser(
      await this.#http.patchJson(`/api/v1/users/${encodeURIComponent(id)}`, {
        is_active: changes.isActive,
        role: changes.role,
      }),
    )
  }
}
