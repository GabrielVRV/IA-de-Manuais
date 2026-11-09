import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { HttpError } from '@/shared/http/errors'
import {
  fakeManualsGateway,
  manual,
  renderApp,
  syncCheck,
  syncRun,
  syncSchedule,
} from '@/test/fakes'

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
    renderApp({ manuals, path: '/admin/manuais' })

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
    renderApp({ manuals, path: '/admin/manuais' })

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
    renderApp({ manuals, path: '/admin/manuais' })

    await user.click(await screen.findByRole('button', { name: 'Reprocessar' }))
    expect(manuals.reindex).toHaveBeenCalledWith('m1', undefined)

    await user.click(screen.getByRole('button', { name: 'Excluir' }))
    expect(confirm).toHaveBeenCalled()
    expect(await screen.findByText(/Nenhum manual cadastrado/)).toBeInTheDocument()
  })

  describe('figures described by AI', () => {
    it('uploads describing the figures only when the option is checked', async () => {
      const user = userEvent.setup()
      const manuals = fakeManualsGateway([])
      renderApp({ manuals, path: '/admin/manuais' })

      await user.upload(await screen.findByLabelText('Escolher PDFs'), pdf('a.pdf'))
      await user.click(screen.getByRole('checkbox', { name: 'Descrever as figuras com IA' }))
      await user.upload(screen.getByLabelText('Escolher PDFs'), pdf('b.pdf'))

      expect(manuals.upload).toHaveBeenNthCalledWith(1, expect.any(File), {
        describeFigures: false,
      })
      expect(manuals.upload).toHaveBeenNthCalledWith(2, expect.any(File), {
        describeFigures: true,
      })
    })

    it('shows the pages to describe and describes an indexed manual', async () => {
      const user = userEvent.setup()
      const manuals = fakeManualsGateway([manual({ figureCount: 1 })])
      const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true)
      renderApp({ manuals, path: '/admin/manuais' })
      expect(await screen.findByText(/12 trechos, 1 página com figuras/)).toBeInTheDocument()

      await user.click(screen.getByRole('button', { name: 'Descrever figuras' }))

      expect(confirm).toHaveBeenCalledWith(expect.stringContaining('3 faltam descrever'))
      expect(manuals.describeFigures).toHaveBeenCalledWith('m1')
      expect(await screen.findByText(/Descrevendo figuras…/)).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Descrever figuras' })).toBeDisabled()
    })

    it('warns when an indexed manual has almost no text (scanned)', async () => {
      const manuals = fakeManualsGateway([
        manual({ id: 'm1', title: 'Siloflex 75', pageCount: 61, chunkCount: 1 }),
        manual({ id: 'm2', title: 'Siloflex 55', pageCount: 62, chunkCount: 60 }),
      ])
      renderApp({ manuals, path: '/admin/manuais' })

      expect(await screen.findByText(/quase não tem texto/)).toBeInTheDocument()
      expect(screen.getAllByText(/quase não tem texto/)).toHaveLength(1)
    })

    it('reprocesses a failed manual (e.g. scanned) describing the figures', async () => {
      const user = userEvent.setup()
      const manuals = fakeManualsGateway([manual({ status: 'failed', pageCount: null })])
      vi.spyOn(window, 'confirm').mockReturnValue(true)
      renderApp({ manuals, path: '/admin/manuais' })

      await user.click(await screen.findByRole('button', { name: 'Descrever figuras' }))

      expect(manuals.reindex).toHaveBeenCalledWith('m1', { describeFigures: true })
      expect(manuals.describeFigures).not.toHaveBeenCalled()
    })

    it('does not call the AI when the figures are already described', async () => {
      const user = userEvent.setup()
      const manuals = fakeManualsGateway([manual()])
      manuals.state.figurePlan = { withFigures: 4, pending: 0 }
      const alert = vi.spyOn(window, 'alert').mockImplementation(() => undefined)
      const confirm = vi.spyOn(window, 'confirm')
      renderApp({ manuals, path: '/admin/manuais' })

      await user.click(await screen.findByRole('button', { name: 'Descrever figuras' }))

      expect(alert).toHaveBeenCalledWith(expect.stringContaining('já estão descritas'))
      expect(confirm).not.toHaveBeenCalled()
      expect(manuals.describeFigures).not.toHaveBeenCalled()
    })

    it('shows why the description of the figures stopped', async () => {
      const manuals = fakeManualsGateway([manual({ figuresError: 'Cota excedida' })])
      renderApp({ manuals, path: '/admin/manuais' })

      expect(
        await screen.findByText('A descrição das figuras parou: Cota excedida'),
      ).toBeInTheDocument()
    })
  })

  it('does not delete when the confirmation is cancelled', async () => {
    const user = userEvent.setup()
    const manuals = fakeManualsGateway([manual()])
    vi.spyOn(window, 'confirm').mockReturnValue(false)
    renderApp({ manuals, path: '/admin/manuais' })

    await user.click(await screen.findByRole('button', { name: 'Excluir' }))

    expect(manuals.remove).not.toHaveBeenCalled()
  })

  it('keeps refreshing while a manual is being indexed', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    try {
      const manuals = fakeManualsGateway([manual({ status: 'processing' })])
      renderApp({ manuals, path: '/admin/manuais' })
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
      renderApp({ manuals, path: '/admin/manuais' })

      await screen.findByRole('list', { name: 'Manuais cadastrados' })
      expect(screen.queryByRole('button', { name: 'Verificar' })).not.toBeInTheDocument()
    })

    it('checks, then syncs after confirmation', async () => {
      const user = userEvent.setup()
      const manuals = fakeManualsGateway()
      const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true)
      renderApp({ manuals, path: '/admin/manuais' })

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

    it('syncs describing the figures when the option is checked', async () => {
      const user = userEvent.setup()
      const manuals = fakeManualsGateway()
      const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true)
      renderApp({ manuals, path: '/admin/manuais' })

      await user.click(await screen.findByRole('button', { name: 'Verificar' }))
      await user.click(
        await screen.findByRole('checkbox', {
          name: 'Descrever as figuras dos manuais novos e alterados',
        }),
      )
      await user.click(screen.getByRole('button', { name: 'Sincronizar' }))

      expect(confirm.mock.calls[0]?.[0]).toMatch(/figuras também serão descritas/)
      expect(manuals.startSync).toHaveBeenCalledWith({ describeFigures: true })
    })

    it('does not sync when the confirmation is cancelled', async () => {
      const user = userEvent.setup()
      const manuals = fakeManualsGateway()
      vi.spyOn(window, 'confirm').mockReturnValue(false)
      renderApp({ manuals, path: '/admin/manuais' })

      await user.click(await screen.findByRole('button', { name: 'Verificar' }))
      await user.click(await screen.findByRole('button', { name: 'Sincronizar' }))

      expect(manuals.startSync).not.toHaveBeenCalled()
    })

    it('says when everything is up to date', async () => {
      const user = userEvent.setup()
      const manuals = fakeManualsGateway()
      manuals.checkSync.mockResolvedValueOnce(
        syncCheck({
          counts: { add: 0, update: 0, retitle: 0, remove: 0, unchanged: 5, ignore: 0, figures: 0 },
          toIndex: 0,
          items: [],
        }),
      )
      renderApp({ manuals, path: '/admin/manuais' })

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
      renderApp({ manuals, path: '/admin/manuais' })

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
        renderApp({ manuals, path: '/admin/manuais' })
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

  describe('daily sync schedule', () => {
    it('turns on the daily sync and shows the next run in the company time', async () => {
      const manuals = fakeManualsGateway()
      const user = userEvent.setup()
      renderApp({ manuals, path: '/admin/manuais' })
      const form = await screen.findByRole('form', { name: 'Sincronização automática' })
      const save = within(form).getByRole('button', { name: 'Salvar agendamento' })
      expect(save).toBeDisabled()

      await user.click(
        within(form).getByRole('checkbox', { name: 'Sincronizar automaticamente todo dia às' }),
      )
      await user.click(save)

      expect(manuals.updateSyncSchedule).toHaveBeenCalledWith({
        enabled: true,
        time: '00:00',
        describeFigures: false,
      })
      expect(
        await within(form).findByText(/Próxima sincronização: 06\/11\/2026,? 00:00/),
      ).toBeInTheDocument()
      expect(within(form).getByText(/Horário de America\/Sao_Paulo/)).toBeInTheDocument()
    })

    it('changes the time of an enabled schedule', async () => {
      const manuals = fakeManualsGateway(undefined, undefined, syncSchedule({ enabled: true }))
      const user = userEvent.setup()
      renderApp({ manuals, path: '/admin/manuais' })
      const time = await screen.findByLabelText('Horário da sincronização')

      await user.clear(time)
      await user.type(time, '06:30')
      await user.click(screen.getByRole('button', { name: 'Salvar agendamento' }))

      expect(manuals.updateSyncSchedule).toHaveBeenCalledWith({
        enabled: true,
        time: '06:30',
        describeFigures: false,
      })
    })

    it('saves the option to also describe the figures', async () => {
      const manuals = fakeManualsGateway(undefined, undefined, syncSchedule({ enabled: true }))
      const user = userEvent.setup()
      renderApp({ manuals, path: '/admin/manuais' })
      const form = await screen.findByRole('form', { name: 'Sincronização automática' })

      await user.click(
        within(form).getByRole('checkbox', {
          name: 'Na sincronização automática, descrever também as figuras',
        }),
      )
      await user.click(within(form).getByRole('button', { name: 'Salvar agendamento' }))

      expect(manuals.updateSyncSchedule).toHaveBeenCalledWith({
        enabled: true,
        time: '00:00',
        describeFigures: true,
      })
    })

    it('warns when the last scheduled sync did not start', async () => {
      const manuals = fakeManualsGateway(
        undefined,
        undefined,
        syncSchedule({
          enabled: true,
          lastTriggeredAt: new Date('2026-11-05T03:00:00Z'),
          lastTriggerError: 'A pasta de manuais está vazia ou não pôde ser lida.',
        }),
      )
      renderApp({ manuals, path: '/admin/manuais' })

      expect(
        await screen.findByText(/A sincronização agendada de 05\/11\/2026,? 00:00 não começou/),
      ).toHaveTextContent('A pasta de manuais está vazia')
    })

    it('shows why the schedule could not be saved', async () => {
      const manuals = fakeManualsGateway()
      manuals.updateSyncSchedule.mockRejectedValueOnce(
        new HttpError(409, {
          detail: 'A pasta de manuais não está configurada (APP_SYNC_SOURCE_DIR).',
        }),
      )
      const user = userEvent.setup()
      renderApp({ manuals, path: '/admin/manuais' })
      const form = await screen.findByRole('form', { name: 'Sincronização automática' })

      await user.click(
        within(form).getByRole('checkbox', { name: 'Sincronizar automaticamente todo dia às' }),
      )
      await user.click(within(form).getByRole('button', { name: 'Salvar agendamento' }))

      expect(await within(form).findByRole('alert')).toHaveTextContent('APP_SYNC_SOURCE_DIR')
    })
  })
})
