import { useCallback, useEffect, useRef, useState } from 'react'

import { describeError } from '@/shared/http/describe-error'
import { HttpError } from '@/shared/http/errors'

import type { SyncCheck, SyncStatus } from '../domain/manuals'
import { useManualsGateway } from './manuals-gateway-context'
import { POLL_INTERVAL_MS } from './use-manuals'

/**
 * Sincronização com a pasta da Engenharia. Enquanto ela roda, a situação é consultada
 * de novo a cada intervalo e ``onProgress`` é chamado (para a lista de manuais acompanhar).
 */
export function useManualSync(onProgress: () => void) {
  const gateway = useManualsGateway()
  const [status, setStatus] = useState<SyncStatus | null>(null)
  const [check, setCheck] = useState<SyncCheck | null>(null)
  const [busy, setBusy] = useState<'checking' | 'starting' | null>(null)
  const [error, setError] = useState<string | null>(null)
  const mounted = useRef(true)
  const progress = useRef(onProgress)
  useEffect(() => {
    progress.current = onProgress
  }, [onProgress])

  useEffect(() => {
    mounted.current = true
    gateway.syncStatus().then(
      (loaded) => {
        if (mounted.current) setStatus(loaded)
      },
      (caught: unknown) => {
        if (mounted.current) setError(describeError(caught))
      },
    )
    return () => {
      mounted.current = false
    }
  }, [gateway])

  const running = status?.running ?? false
  useEffect(() => {
    if (!running) return
    const timer = setInterval(() => {
      gateway.syncStatus().then(
        (loaded) => {
          if (!mounted.current) return
          setStatus(loaded)
          progress.current()
        },
        () => {
          // Falha momentânea: tenta de novo no próximo intervalo.
        },
      )
    }, POLL_INTERVAL_MS)
    return () => {
      clearInterval(timer)
    }
  }, [running, gateway])

  const verify = useCallback(async () => {
    setBusy('checking')
    setError(null)
    try {
      const result = await gateway.checkSync()
      if (mounted.current) setCheck(result)
    } catch (caught) {
      if (mounted.current) setError(describeSyncError(caught))
    } finally {
      if (mounted.current) setBusy(null)
    }
  }, [gateway])

  const start = useCallback(async () => {
    setBusy('starting')
    setError(null)
    try {
      const run = await gateway.startSync()
      if (!mounted.current) return
      setCheck(null)
      setStatus((current) => ({ enabled: current?.enabled ?? true, running: true, lastRun: run }))
      progress.current()
    } catch (caught) {
      if (mounted.current) setError(describeSyncError(caught))
    } finally {
      if (mounted.current) setBusy(null)
    }
  }, [gateway])

  return {
    status,
    check,
    busy,
    error,
    verify,
    start,
    dismissCheck: () => {
      setCheck(null)
    },
  }
}

/** O 503 da sincronização é quase sempre a pasta de rede: vale dizer isso ao administrador
 * (o detalhe técnico fica nos logs do servidor). */
function describeSyncError(error: unknown): string {
  if (error instanceof HttpError && error.status === 503) {
    return 'Não foi possível ler a pasta de manuais no servidor (vazia ou inacessível). Confira se ela está montada e tente de novo. Nada foi alterado.'
  }
  return describeError(error)
}
