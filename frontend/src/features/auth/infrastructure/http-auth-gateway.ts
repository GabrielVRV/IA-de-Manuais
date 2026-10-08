import { z } from 'zod'

import { HttpError, InvalidResponseError } from '@/shared/http/errors'
import type { HttpClient } from '@/shared/http/http-client'

import type { AuthGateway, SessionUser } from '../domain/auth'

const userSchema = z.object({
  id: z.string(),
  username: z.string(),
  display_name: z.string(),
  role: z.enum(['admin', 'user']),
  must_change_password: z.boolean(),
})

export function toSessionUser(body: unknown): SessionUser {
  const result = userSchema.safeParse(body)
  if (!result.success) throw new InvalidResponseError({ cause: result.error })
  const user = result.data
  return {
    id: user.id,
    username: user.username,
    displayName: user.display_name,
    role: user.role,
    mustChangePassword: user.must_change_password,
  }
}

export class HttpAuthGateway implements AuthGateway {
  readonly #http: HttpClient
  readonly #listeners = new Set<() => void>()

  constructor(http: HttpClient) {
    this.#http = http
    http.setUnauthorizedHandler(() => {
      for (const listener of this.#listeners) listener()
    })
  }

  async currentUser(): Promise<SessionUser | null> {
    try {
      return toSessionUser(await this.#http.getJson('/api/v1/auth/me'))
    } catch (error) {
      if (error instanceof HttpError && error.status === 401) return null
      throw error
    }
  }

  async login(username: string, password: string): Promise<SessionUser> {
    return toSessionUser(await this.#http.postJson('/api/v1/auth/login', { username, password }))
  }

  async logout(): Promise<void> {
    await this.#http.postJson('/api/v1/auth/logout')
  }

  async changePassword(currentPassword: string, newPassword: string): Promise<void> {
    await this.#http.postJson('/api/v1/auth/change-password', {
      current_password: currentPassword,
      new_password: newPassword,
    })
  }

  onSessionExpired(listener: () => void): () => void {
    this.#listeners.add(listener)
    return () => {
      this.#listeners.delete(listener)
    }
  }
}
