import { type DragEvent, useState } from 'react'

import { cx } from '@/shared/cx'
import ui from '@/styles/ui.module.css'

import type { ManualStatus, ManualSummary } from '../domain/manuals'
import styles from './ManualsAdmin.module.css'
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

export function ManualsAdmin() {
  const { manuals, error, uploads, upload, reindex, remove, fileUrl, clearUploads } = useManuals()
  const sending = uploads.some((u) => u.status === 'sending')

  return (
    <div className={ui.page}>
      <header className={ui.pageHeader}>
        <h2 className={ui.pageTitle}>Manuais</h2>
        {manuals && <Summary manuals={manuals} />}
      </header>

      <div className={ui.stack}>
        <DropZone
          disabled={sending}
          onFiles={(files) => {
            void upload(files)
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
  onFiles,
}: {
  readonly disabled: boolean
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
    </div>
  )
}

interface ManualItemProps {
  readonly manual: ManualSummary
  readonly fileUrl: string
  readonly onReindex: () => void
  readonly onRemove: () => void
}

function ManualItem({ manual, fileUrl, onReindex, onRemove }: ManualItemProps) {
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
        </div>
        <span className={ui.muted}>
          {manual.fileName} · enviado em {dateFormat.format(manual.createdAt)}
          {manual.status === 'indexed' &&
            ` · ${plural(manual.pageCount, 'página', 'páginas')}, ${plural(manual.chunkCount, 'trecho', 'trechos')}`}
        </span>
        {manual.failureReason && <span className={styles.reason}>{manual.failureReason}</span>}
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
