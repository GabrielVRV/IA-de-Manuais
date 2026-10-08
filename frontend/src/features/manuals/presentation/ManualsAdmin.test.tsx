import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { HttpError } from '@/shared/http/errors'
import { fakeManualsGateway, manual, renderApp } from '@/test/fakes'

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
})
