import { type DragEvent, useState } from 'react'

import { cx } from '@/shared/cx'
import ui from '@/styles/ui.module.css'

import {
  type FigurePlan,
  type ManualStatus,
  type ManualSummary,
  needsFigureDescription,
} from '../domain/manuals'
import styles from './ManualsAdmin.module.css'
import { FigureCheckbox } from './FigureCheckbox'
import { SyncPanel } from './SyncPanel'
import { useManuals } from './use-manuals'

const STATUS: Record<ManualStatus, { label: string; tone: string }> = {
  pending: { label: 'Na fila', tone: 'neutral' },
  processing: { label: 'Indexando…', tone: 'info' },
  indexed: { label: 'Disponível', tone: 'success' },
  failed: { label: 'Falhou', tone: 'danger' },
}

const dateFormat = new Intl.DateTimeFormat('pt-BR', { dateStyle: 'short', timeStyle: 'short' })

const plural = (count: number | null, one: string, many: string) =>
  `${String(count)} ${count === 1 ? one : many}`

/** Texto da confirmação antes de mandar as figuras para a IA (cada página é uma chamada). */
function figureQuestion(manual: ManualSummary, plan: FigurePlan): string {
  const lines = [
    `Descrever as figuras de "${manual.title}" com IA?`,
    `${plural(plan.withFigures, 'página tem', 'páginas têm')} figuras; ${plural(plan.pending, 'falta', 'faltam')} descrever (uma chamada de IA por página).`,
  ]
  if (manual.status !== 'indexed') lines.push('O manual será reprocessado.')
  return lines.join('\n')
}

export function ManualsAdmin() {
  const {
    manuals,
    error,
    uploads,
    upload,
    reindex,
    describeFigures,
    figurePlan,
    remove,
    fileUrl,
    clearUploads,
    refresh,
  } = useManuals()
  const [describeOnUpload, setDescribeOnUpload] = useState(false)
  const sending = uploads.some((u) => u.status === 'sending')

  const askAndDescribe = async (manual: ManualSummary) => {
    const plan = await figurePlan(manual.id)
    if (!plan) return
    if (plan.withFigures === 0) {
      window.alert(`Nenhuma página de "${manual.title}" tem figuras para descrever.`)
      return
    }
    if (manual.status === 'indexed' && plan.pending === 0) {
      window.alert(`As figuras de "${manual.title}" já estão descritas.`)
      return
    }
    if (!window.confirm(figureQuestion(manual, plan))) return
    // Indexado: só acrescenta as figuras. Com falha (ex.: escaneado): reprocessa com elas.
    await (manual.status === 'indexed'
      ? describeFigures(manual.id)
      : reindex(manual.id, { describeFigures: true }))
  }

  return (
    <div className={ui.page}>
      <header className={ui.pageHeader}>
        <h2 className={ui.pageTitle}>Manuais</h2>
        {manuals && <Summary manuals={manuals} />}
      </header>

      <div className={ui.stack}>
        <SyncPanel onProgress={() => void refresh()} />

        <DropZone
          disabled={sending}
          describeFigures={describeOnUpload}
          onDescribeFiguresChange={setDescribeOnUpload}
          onFiles={(files) => {
            void upload(files, { describeFigures: describeOnUpload })
          }}
        />

        {uploads.length > 0 && (
          <div className={ui.card}>
            <ul className={styles.uploads} aria-label="Envios">
              {uploads.map((item, index) => (
                <li key={`${item.fileName}-${String(index)}`}>
                  <span className={ui.badge} data-tone={UPLOAD_TONE[item.status]}>
                    {UPLOAD_LABEL[item.status]}
                  </span>{' '}
                  {item.fileName}
                  {item.message && <span className={styles.reason}> — {item.message}</span>}
                </li>
              ))}
            </ul>
            {!sending && (
              <button type="button" className={ui.button} onClick={clearUploads}>
                Limpar lista
              </button>
            )}
          </div>
        )}

        {error && (
          <p className={ui.alert} data-tone="danger" role="alert">
            {error}
          </p>
        )}

        {manuals === null && !error && <p className={ui.muted}>Carregando manuais…</p>}
        {manuals?.length === 0 && (
          <p className={ui.muted}>Nenhum manual cadastrado ainda. Envie o primeiro PDF acima.</p>
        )}

        {manuals && manuals.length > 0 && (
          <ul className={styles.list} aria-label="Manuais cadastrados">
            {manuals.map((manual) => (
              <ManualItem
                key={manual.id}
                manual={manual}
                fileUrl={fileUrl(manual.id)}
                onReindex={() => void reindex(manual.id)}
                onDescribeFigures={() => void askAndDescribe(manual)}
                onRemove={() => {
                  if (window.confirm(`Excluir "${manual.title}"? Ele deixará de ser consultado.`)) {
                    void remove(manual.id)
                  }
                }}
              />
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}

const UPLOAD_LABEL = { sending: 'Enviando', sent: 'Enviado', rejected: 'Recusado' } as const
const UPLOAD_TONE = { sending: 'info', sent: 'success', rejected: 'danger' } as const

function Summary({ manuals }: { readonly manuals: readonly ManualSummary[] }) {
  const available = manuals.filter((m) => m.status === 'indexed').length
  const failed = manuals.filter((m) => m.status === 'failed').length
  return (
    <span className={ui.muted}>
      {available} disponível(is) de {manuals.length}
      {failed > 0 && ` · ${String(failed)} com falha`}
    </span>
  )
}

function DropZone({
  disabled,
  describeFigures,
  onDescribeFiguresChange,
  onFiles,
}: {
  readonly disabled: boolean
  readonly describeFigures: boolean
  readonly onDescribeFiguresChange: (value: boolean) => void
  readonly onFiles: (files: File[]) => void
}) {
  const [dragging, setDragging] = useState(false)

  const accept = (files: FileList | null) => {
    const pdfs = Array.from(files ?? []).filter((f) => f.name.toLowerCase().endsWith('.pdf'))
    if (pdfs.length > 0) onFiles(pdfs)
  }

  const onDrop = (event: DragEvent) => {
    event.preventDefault()
    setDragging(false)
    if (!disabled) accept(event.dataTransfer.files)
  }

  return (
    <div
      className={cx(styles.dropZone, dragging && styles.dragging)}
      onDragOver={(event) => {
        event.preventDefault()
        setDragging(true)
      }}
      onDragLeave={() => {
        setDragging(false)
      }}
      onDrop={onDrop}
    >
      <p className={styles.dropTitle}>Arraste os PDFs dos manuais para cá</p>
      <p className={ui.muted}>
        Ou escolha um ou mais arquivos. Cada manual é indexado em segundo plano.
      </p>
      <label className={cx(ui.button, ui.primary, disabled && styles.disabled)}>
        {disabled ? 'Enviando…' : 'Escolher PDFs'}
        <input
          className={ui.visuallyHidden}
          type="file"
          accept="application/pdf,.pdf"
          multiple
          disabled={disabled}
          onChange={(event) => {
            accept(event.target.files)
            event.target.value = '' // permite escolher o mesmo arquivo de novo
          }}
        />
      </label>
      <FigureCheckbox
        checked={describeFigures}
        disabled={disabled}
        onChange={onDescribeFiguresChange}
      />
    </div>
  )
}

interface ManualItemProps {
  readonly manual: ManualSummary
  readonly fileUrl: string
  readonly onReindex: () => void
  readonly onDescribeFigures: () => void
  readonly onRemove: () => void
}

function ManualItem({ manual, fileUrl, onReindex, onDescribeFigures, onRemove }: ManualItemProps) {
  const status = STATUS[manual.status]
  const busy = manual.status === 'pending' || manual.status === 'processing'

  return (
    <li className={cx(ui.card, styles.item)}>
      <div className={styles.itemMain}>
        <div className={styles.itemTitle}>
          <strong>{manual.title}</strong>
          <span className={ui.badge} data-tone={status.tone}>
            {status.label}
          </span>
          {manual.describingFigures && (
            <span className={ui.badge} data-tone="info">
              Descrevendo figuras… {manual.figuresDescribed}
            </span>
          )}
        </div>
        <span className={ui.muted}>
          {manual.fileName} · enviado em {dateFormat.format(manual.createdAt)}
          {manual.status === 'indexed' &&
            ` · ${plural(manual.pageCount, 'página', 'páginas')}, ${plural(manual.chunkCount, 'trecho', 'trechos')}`}
          {manual.status === 'indexed' &&
            Boolean(manual.figureCount) &&
            `, ${plural(manual.figureCount, 'página com figuras', 'páginas com figuras')}`}
        </span>
        {manual.failureReason && <span className={styles.reason}>{manual.failureReason}</span>}
        {needsFigureDescription(manual) && !manual.describingFigures && (
          <span className={styles.reason}>
            Este PDF quase não tem texto (parece escaneado): a IA só enxerga a capa. Clique em
            Descrever figuras para ela ler as páginas.
          </span>
        )}
        {manual.figuresError && !manual.describingFigures && (
          <span className={styles.reason}>
            A descrição das figuras parou: {manual.figuresError}
          </span>
        )}
      </div>
      <div className={styles.actions}>
        <a className={ui.button} href={fileUrl} target="_blank" rel="noopener noreferrer">
          Abrir PDF
        </a>
        <button type="button" className={ui.button} onClick={onReindex} disabled={busy}>
          Reprocessar
        </button>
        <button
          type="button"
          className={ui.button}
          onClick={onDescribeFigures}
          disabled={busy || manual.describingFigures}
        >
          Descrever figuras
        </button>
        <button
          type="button"
          className={cx(ui.button, ui.danger)}
          onClick={onRemove}
          disabled={busy}
        >
          Excluir
        </button>
      </div>
    </li>
  )
}
