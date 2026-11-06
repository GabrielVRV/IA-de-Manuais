import { useCallback, useEffect, useRef, useState } from 'react'

import { describeError } from '@/shared/http/describe-error'

import {
  type FigureOption,
  type FigurePlan,
  isInProgress,
  type ManualSummary,
} from '../domain/manuals'
import { useManualsGateway } from './manuals-gateway-context'

/** Enquanto houver manual sendo indexado, a lista se atualiza sozinha neste intervalo. */
export const POLL_INTERVAL_MS = 3000

export interface UploadResult {
  readonly fileName: string
  readonly status: 'sending' | 'sent' | 'rejected'
  readonly message?: string
}

export function useManuals() {
  const gateway = useManualsGateway()
  const [manuals, setManuals] = useState<ManualSummary[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [uploads, setUploads] = useState<UploadResult[]>([])
  const mounted = useRef(true)

  const refresh = useCallback(async () => {
    try {
      const list = await gateway.list()
      if (!mounted.current) return
      setManuals(list)
      setError(null)
    } catch (caught) {
      if (mounted.current) setError(describeError(caught))
    }
  }, [gateway])

  // Carga inicial: o estado só muda nos callbacks da promessa, nunca no corpo do efeito.
  useEffect(() => {
    mounted.current = true
    gateway.list().then(
      (list) => {
        if (mounted.current) setManuals(list)
      },
      (caught: unknown) => {
        if (mounted.current) setError(describeError(caught))
      },
    )
    return () => {
      mounted.current = false
    }
  }, [gateway])

  const hasWorkInProgress = manuals?.some(isInProgress) ?? false
  useEffect(() => {
    if (!hasWorkInProgress) return
    const timer = setInterval(() => void refresh(), POLL_INTERVAL_MS)
    return () => {
      clearInterval(timer)
    }
  }, [hasWorkInProgress, refresh])

  const upload = useCallback(
    async (files: readonly File[], option?: FigureOption) => {
      setUploads(files.map((file) => ({ fileName: file.name, status: 'sending' })))
      // Um por vez: o servidor indexa em segundo plano, e o envio sequencial não o sobrecarrega.
      for (const [index, file] of files.entries()) {
        let result: UploadResult
        try {
          await gateway.upload(file, option)
          result = { fileName: file.name, status: 'sent' }
        } catch (caught) {
          result = { fileName: file.name, status: 'rejected', message: describeError(caught) }
        }
        setUploads((current) => current.map((item, i) => (i === index ? result : item)))
        await refresh()
      }
    },
    [gateway, refresh],
  )

  const act = useCallback(
    async (action: () => Promise<unknown>) => {
      try {
        await action()
      } catch (caught) {
        setError(describeError(caught))
      }
      await refresh()
    },
    [refresh],
  )

  return {
    manuals,
    error,
    uploads,
    upload,
    refresh,
    reindex: (id: string, option?: FigureOption) => act(() => gateway.reindex(id, option)),
    describeFigures: (id: string) => act(() => gateway.describeFigures(id)),
    /** Conta as páginas com figuras (sem chamar a IA); null se não deu para ler o PDF. */
    figurePlan: async (id: string): Promise<FigurePlan | null> => {
      try {
        return await gateway.figurePlan(id)
      } catch (caught) {
        setError(describeError(caught))
        return null
      }
    },
    remove: (id: string) => act(() => gateway.remove(id)),
    fileUrl: (id: string) => gateway.fileUrl(id),
    clearUploads: () => {
      setUploads([])
    },
  }
}
