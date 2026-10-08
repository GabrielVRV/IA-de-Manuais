import { describe, expect, it, vi } from 'vitest'

import { HttpError } from '@/shared/http/errors'
import { HttpClient } from '@/shared/http/http-client'

import { HttpAuthGateway } from './http-auth-gateway'

const apiUser = {
  id: 'u1',
  username: 'maria',
  display_name: 'Maria Silva',
  role: 'admin',
  must_change_password: false,
  is_active: true,
}

function gateway(...responses: Response[]) {
  const fetchFn = vi.fn<typeof fetch>()
  for (const response of responses) fetchFn.mockResolvedValueOnce(response)
  return { gateway: new HttpAuthGateway(new HttpClient('http://api', { fetchFn })), fetchFn }
}

describe('HttpAuthGateway', () => {
  it('logs in and maps the user', async () => {
    const { gateway: auth, fetchFn } = gateway(Response.json(apiUser))

    const user = await auth.login('maria', 'senha-forte')

    expect(user).toEqual({
      id: 'u1',
      username: 'maria',
      displayName: 'Maria Silva',
      role: 'admin',
      mustChangePassword: false,
    })
    expect(fetchFn).toHaveBeenCalledWith(
      'http://api/api/v1/auth/login',
      expect.objectContaining({ body: '{"username":"maria","password":"senha-forte"}' }),
    )
  })

  it('treats a 401 on /me as "nobody logged in"', async () => {
    const { gateway: auth } = gateway(Response.json({ detail: 'Faça login' }, { status: 401 }))

    await expect(auth.currentUser()).resolves.toBeNull()
  })

  it('propagates other failures when checking the session', async () => {
    const { gateway: auth } = gateway(Response.json({}, { status: 500 }))

    await expect(auth.currentUser()).rejects.toBeInstanceOf(HttpError)
  })

  it('notifies listeners when any request comes back 401', async () => {
    const { gateway: auth } = gateway(Response.json({}, { status: 401 }))
    const listener = vi.fn()
    const unsubscribe = auth.onSessionExpired(listener)

    await auth.changePassword('a', 'b').catch(() => undefined)
    unsubscribe()

    expect(listener).toHaveBeenCalledOnce()
  })

  it('sends the password change in the API format', async () => {
    const { gateway: auth, fetchFn } = gateway(new Response(null, { status: 204 }))

    await auth.changePassword('atual-123', 'nova-senha-1')

    expect(fetchFn).toHaveBeenCalledWith(
      'http://api/api/v1/auth/change-password',
      expect.objectContaining({
        body: '{"current_password":"atual-123","new_password":"nova-senha-1"}',
      }),
    )
  })
})
