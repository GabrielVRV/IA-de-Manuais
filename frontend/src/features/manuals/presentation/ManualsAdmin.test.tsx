import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { HttpError } from '@/shared/http/errors'
import { fakeManualsGateway, manual, renderApp, syncCheck, syncRun } from '@/test/fakes'

const pdf = (name: string) => new File(['%PDF-1.4'], name, { type: 'application/pdf' })

describe('<ManualsAdmin />', () => {
  it('lists manuals with their status and failure reason', async () => {
    const manuals = fakeManualsGateway([
      manual(),
      manual({
        id: 'm2',
        title: 'Prensa P-200',
        status: 'failed',
        failureReason: 'PDF protegido por senha',
      }),
    ])
    renderApp({ manuals, path: '/manuais' })

    const list = await screen.findByRole('list', { name: 'Manuais cadastrados' })
    expect(within(list).getByText('Compressor CX-500')).toBeInTheDocument()
    expect(within(list).getByText('Disponível')).toBeInTheDocument()
    expect(within(list).getByText(/7 páginas, 12 trechos/)).toBeInTheDocument()
    expect(within(list).getByText('Falhou')).toBeInTheDocument()
    expect(within(list).getByText('PDF protegido por senha')).toBeInTheDocument()
    expect(screen.getByText(/1 disponível\(is\) de 2 · 1 com falha/)).toBeInTheDocument()
    expect(within(list).getAllByRole('link', { name: 'Abrir PDF' })[0]).toHaveAttribute(
      'href',
      'http://api/manuals/m1/file',
    )
  })

  it('uploads several PDFs and reports each one', async () => {
    const user = userEvent.setup()
    const manuals = fakeManualsGateway([])
    manuals.upload.mockRejectedValueOnce(
      new HttpError(422, { detail: 'O arquivo enviado não é um PDF' }),
    )
    renderApp({ manuals, path: '/manuais' })

    await user.upload(await screen.findByLabelText('Escolher PDFs'), [
      pdf('ruim.pdf'),
      pdf('torno.pdf'),
    ])

    const uploads = screen.getByRole('list', { name: 'Envios' })
    expect(await within(uploads).findByText('Enviado')).toBeInTheDocument()
    expect(within(uploads).getByText(/não é um PDF/)).toBeInTheDocument()
    expect(manuals.upload).toHaveBeenCalledTimes(2)
    expect(await screen.findByText('Indexando…')).toBeInTheDocument()
  })

  it('reindexes and deletes after confirmation', async () => {
    const user = userEvent.setup()
    const manuals = fakeManualsGateway([manual()])
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true)
    renderApp({ manuals, path: '/manuais' })

    await user.click(await screen.findByRole('button', { name: 'Reprocessar' }))
    expect(manuals.reindex).toHaveBeenCalledWith('m1')

    await user.click(screen.getByRole('button', { name: 'Excluir' }))
    expect(confirm).toHaveBeenCalled()
    expect(await screen.findByText(/Nenhum manual cadastrado/)).toBeInTheDocument()
  })

  it('does not delete when the confirmation is cancelled', async () => {
    const user = userEvent.setup()
    const manuals = fakeManualsGateway([manual()])
    vi.spyOn(window, 'confirm').mockReturnValue(false)
    renderApp({ manuals, path: '/manuais' })

    await user.click(await screen.findByRole('button', { name: 'Excluir' }))

    expect(manuals.remove).not.toHaveBeenCalled()
  })

  it('keeps refreshing while a manual is being indexed', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    try {
      const manuals = fakeManualsGateway([manual({ status: 'processing' })])
      renderApp({ manuals, path: '/manuais' })
      expect(await screen.findByText('Indexando…')).toBeInTheDocument()

      manuals.state.manuals = [manual({ status: 'indexed' })]
      await vi.advanceTimersByTimeAsync(3000)

      expect(await screen.findByText('Disponível')).toBeInTheDocument()
    } finally {
      vi.useRealTimers()
    }
  })

  describe('sync with the Engineering folder', () => {
    it('is hidden when the folder is not configured', async () => {
      const manuals = fakeManualsGateway([manual()], {
        enabled: false,
        running: false,
        lastRun: null,
      })
      renderApp({ manuals, path: '/manuais' })

      await screen.findByRole('list', { name: 'Manuais cadastrados' })
      expect(screen.queryByRole('button', { name: 'Verificar' })).not.toBeInTheDocument()
    })

    it('checks, then syncs after confirmation', async () => {
      const user = userEvent.setup()
      const manuals = fakeManualsGateway()
      const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true)
      renderApp({ manuals, path: '/manuais' })

      await user.click(await screen.findByRole('button', { name: 'Verificar' }))

      const result = await screen.findByRole('list', { name: 'Resultado da verificação' })
      expect(within(result).getByText(/novo\(s\)/)).toBeInTheDocument()
      expect(within(result).getByText(/5 sem mudança/)).toBeInTheDocument()
      expect(screen.getByText('Ver ignorados (1)')).toBeInTheDocument()
      expect(manuals.startSync).not.toHaveBeenCalled()

      await user.click(screen.getByRole('button', { name: 'Sincronizar' }))

      expect(confirm.mock.calls[0]?.[0]).toMatch(/1 manual\(is\) serão indexados/)
      expect(manuals.startSync).toHaveBeenCalledTimes(1)
      expect(await screen.findByText(/Sincronizando… 0 de 1/)).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Verificar' })).toBeDisabled()
    })

    it('does not sync when the confirmation is cancelled', async () => {
      const user = userEvent.setup()
      const manuals = fakeManualsGateway()
      vi.spyOn(window, 'confirm').mockReturnValue(false)
      renderApp({ manuals, path: '/manuais' })

      await user.click(await screen.findByRole('button', { name: 'Verificar' }))
      await user.click(await screen.findByRole('button', { name: 'Sincronizar' }))

      expect(manuals.startSync).not.toHaveBeenCalled()
    })

    it('says when everything is up to date', async () => {
      const user = userEvent.setup()
      const manuals = fakeManualsGateway()
      manuals.checkSync.mockResolvedValueOnce(
        syncCheck({
          counts: { add: 0, update: 0, retitle: 0, remove: 0, unchanged: 5, ignore: 0 },
          toIndex: 0,
          items: [],
        }),
      )
      renderApp({ manuals, path: '/manuais' })

      await user.click(await screen.findByRole('button', { name: 'Verificar' }))

      expect(await screen.findByText(/Tudo em dia/)).toBeInTheDocument()
      expect(screen.queryByRole('button', { name: 'Sincronizar' })).not.toBeInTheDocument()
    })

    it('shows an error when the folder cannot be read', async () => {
      const user = userEvent.setup()
      const manuals = fakeManualsGateway()
      manuals.checkSync.mockRejectedValueOnce(
        new HttpError(503, { detail: 'A pasta de manuais está vazia ou não pôde ser lida.' }),
      )
      renderApp({ manuals, path: '/manuais' })

      await user.click(await screen.findByRole('button', { name: 'Verificar' }))

      expect(await screen.findByText(/Não foi possível ler a pasta/)).toBeInTheDocument()
    })

    it('follows the sync until it finishes and shows the failures', async () => {
      vi.useFakeTimers({ shouldAdvanceTime: true })
      try {
        const manuals = fakeManualsGateway([], {
          enabled: true,
          running: true,
          lastRun: syncRun({ total: 2, done: 1, succeeded: 1 }),
        })
        renderApp({ manuals, path: '/manuais' })
        expect(await screen.findByText(/Sincronizando… 1 de 2/)).toBeInTheDocument()

        manuals.state.manuals = [manual()]
        manuals.state.sync = {
          enabled: true,
          running: false,
          lastRun: syncRun({
            running: false,
            finishedAt: new Date('2026-10-16T10:05:00Z'),
            total: 2,
            done: 2,
            succeeded: 1,
            failures: [{ action: 'add', fileName: 'ruim.pdf', detail: 'não é um PDF' }],
          }),
        }
        await vi.advanceTimersByTimeAsync(3000)

        expect(await screen.findByText(/Última sincronização/)).toHaveTextContent(
          /por Ana Admin\. 1 ok, 1 com falha/,
        )
        expect(screen.getByText('Ver falhas (1)')).toBeInTheDocument()
        // A lista de manuais acompanha a sincronização.
        expect(await screen.findByText('Compressor CX-500')).toBeInTheDocument()
      } finally {
        vi.useRealTimers()
      }
    })
  })
})
