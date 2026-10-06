import { useCallback, useEffect, useState } from 'react'

import { describeError } from '@/shared/http/describe-error'

import type { ApiHealth } from '../domain/api-health'
import { useHealthGateway } from './health-gateway-context'

export type ApiHealthState =
  | { readonly kind: 'checking' }
  | { readonly kind: 'reachable'; readonly health: ApiHealth }
  | { readonly kind: 'unreachable'; readonly message: string }

export function useApiHealth(): { state: ApiHealthState; recheck: () => void } {
  const gateway = useHealthGateway()
  const [state, setState] = useState<ApiHealthState>({ kind: 'checking' })
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    const controller = new AbortController()

    gateway.check(controller.signal).then(
      (health) => {
        if (!controller.signal.aborted) setState({ kind: 'reachable', health })
      },
      (error: unknown) => {
        if (!controller.signal.aborted) {
          setState({ kind: 'unreachable', message: describeError(error) })
        }
      },
    )

    return () => {
      controller.abort()
    }
  }, [gateway, attempt])

  const recheck = useCallback(() => {
    setState({ kind: 'checking' })
    setAttempt((n) => n + 1)
  }, [])

  return { state, recheck }
}
