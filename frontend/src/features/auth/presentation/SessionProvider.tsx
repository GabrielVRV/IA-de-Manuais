import { type ReactNode, useCallback, useEffect, useMemo, useState } from 'react'

import { type Session, SessionContext, type SessionState, useAuthGateway } from './session-context'

const EXPIRED_NOTICE = 'Sua sessão expirou. Entre novamente para continuar.'

export function SessionProvider({ children }: { readonly children: ReactNode }) {
  const gateway = useAuthGateway()
  const [state, setState] = useState<SessionState>({ status: 'loading' })

  useEffect(() => {
    let active = true
    gateway.currentUser().then(
      (user) => {
        if (active) setState(user ? { status: 'authenticated', user } : { status: 'anonymous' })
      },
      () => {
        // API fora do ar: mostra o login; o erro aparece ao tentar entrar.
        if (active) setState({ status: 'anonymous' })
      },
    )
    const unsubscribe = gateway.onSessionExpired(() => {
      setState((current) =>
        current.status === 'authenticated'
          ? { status: 'anonymous', notice: EXPIRED_NOTICE }
          : current,
      )
    })
    return () => {
      active = false
      unsubscribe()
    }
  }, [gateway])

  const login = useCallback(
    async (username: string, password: string) => {
      const user = await gateway.login(username, password)
      setState({ status: 'authenticated', user })
    },
    [gateway],
  )

  const logout = useCallback(async () => {
    try {
      await gateway.logout()
    } finally {
      setState({ status: 'anonymous' })
    }
  }, [gateway])

  const refresh = useCallback(async () => {
    const user = await gateway.currentUser()
    setState(user ? { status: 'authenticated', user } : { status: 'anonymous' })
  }, [gateway])

  const changePassword = useCallback(
    async (currentPassword: string, newPassword: string) => {
      await gateway.changePassword(currentPassword, newPassword)
      setState((current) =>
        current.status === 'authenticated'
          ? { status: 'authenticated', user: { ...current.user, mustChangePassword: false } }
          : current,
      )
    },
    [gateway],
  )

  const session = useMemo<Session>(
    () => ({ state, login, logout, refresh, changePassword }),
    [state, login, logout, refresh, changePassword],
  )

  return <SessionContext value={session}>{children}</SessionContext>
}
