import { cx } from '@/shared/cx'
import ui from '@/styles/ui.module.css'

import { hasPendingChanges, type SyncAction, type SyncCheck, type SyncRun } from '../domain/manuals'
import styles from './ManualsAdmin.module.css'
import { useManualSync } from './use-manual-sync'

const dateFormat = new Intl.DateTimeFormat('pt-BR', { dateStyle: 'short', timeStyle: 'short' })

/** Ordem e textos do resumo da verificação ("unchanged" aparece à parte). */
const SUMMARY: readonly (readonly [SyncAction, string])[] = [
  ['add', 'novo(s)'],
  ['update', 'com revisão ou arquivo novo'],
  ['retitle', 'com título novo na planilha'],
  ['remove', 'a remover do sistema (saíram da pasta)'],
  ['ignore', 'ignorado(s)'],
]

const ACTION: Record<SyncAction, { label: string; tone: string }> = {
  add: { label: 'Novo', tone: 'success' },
  update: { label: 'Atualizar', tone: 'info' },
  retitle: { label: 'Título', tone: 'neutral' },
  remove: { label: 'Remover', tone: 'danger' },
  unchanged: { label: 'Sem mudança', tone: 'neutral' },
  ignore: { label: 'Ignorado', tone: 'neutral' },
}

/** Verificar e sincronizar com a pasta de manuais da Engenharia (só leitura). */
export function SyncPanel({ onProgress }: { readonly onProgress: () => void }) {
  const { status, check, busy, error, verify, start, dismissCheck } = useManualSync(onProgress)

  // Pasta não configurada no servidor: o painel não aparece.
  if (status && !status.enabled) return null

  const running = status?.running ?? false
  const lastRun = status?.lastRun ?? null

  const confirmAndStart = (pending: SyncCheck) => {
    const lines = [
      'Sincronizar com a pasta da Engenharia?',
      `${String(pending.toIndex)} manual(is) serão indexados (gasta API de IA).`,
    ]
    if (pending.counts.remove > 0) {
      lines.push(`${String(pending.counts.remove)} manual(is) sairão do sistema.`)
    }
    lines.push('A pasta não é alterada.')
    if (window.confirm(lines.join('\n'))) void start()
  }

  return (
    <section className={cx(ui.card, styles.sync)} aria-label="Pasta da Engenharia">
      <div className={styles.syncHeader}>
        <div className={styles.itemMain}>
          <strong>Pasta de manuais da Engenharia</strong>
          <span className={ui.muted}>
            Compara a pasta com os manuais cadastrados. A pasta só é lida, nunca alterada.
          </span>
        </div>
        <button
          type="button"
          className={ui.button}
          onClick={() => void verify()}
          disabled={!status || running || busy !== null}
        >
          {busy === 'checking' ? 'Verificando…' : 'Verificar'}
        </button>
      </div>

      {error && (
        <p className={ui.alert} data-tone="danger" role="alert">
          {error}
        </p>
      )}

      {check && !running && (
        <CheckResult
          check={check}
          starting={busy === 'starting'}
          onStart={() => {
            confirmAndStart(check)
          }}
          onDismiss={dismissCheck}
        />
      )}

      {lastRun && <RunResult run={lastRun} />}
    </section>
  )
}

function CheckResult({
  check,
  starting,
  onStart,
  onDismiss,
}: {
  readonly check: SyncCheck
  readonly starting: boolean
  readonly onStart: () => void
  readonly onDismiss: () => void
}) {
  const pending = hasPendingChanges(check)
  const changes = check.items.filter((item) => item.action !== 'ignore')
  const ignored = check.items.filter((item) => item.action === 'ignore')

  return (
    <div className={styles.syncResult}>
      {pending ? (
        <ul className={styles.syncCounts} aria-label="Resultado da verificação">
          {SUMMARY.filter(([action]) => check.counts[action] > 0).map(([action, label]) => (
            <li key={action}>
              <strong>{check.counts[action]}</strong> {label}
            </li>
          ))}
          <li className={ui.muted}>{check.counts.unchanged} sem mudança</li>
        </ul>
      ) : (
        <p className={ui.alert} data-tone="success" role="status">
          Tudo em dia: nenhum manual novo, alterado ou removido ({check.counts.unchanged} sem
          mudança).
        </p>
      )}

      {changes.length > 0 && (
        <details>
          <summary>Ver o que muda ({changes.length})</summary>
          <ul className={styles.uploads}>
            {changes.map((item) => (
              <li key={`${item.action}-${item.fileName}`}>
                <span className={ui.badge} data-tone={ACTION[item.action].tone}>
                  {ACTION[item.action].label}
                </span>{' '}
                {item.fileName}
                {item.title && item.title !== item.fileName && (
                  <span className={ui.muted}> — {item.title}</span>
                )}
              </li>
            ))}
          </ul>
        </details>
      )}

      {ignored.length > 0 && (
        <details>
          <summary>Ver ignorados ({ignored.length})</summary>
          <ul className={styles.uploads}>
            {ignored.map((item, index) => (
              <li key={`${item.fileName}-${String(index)}`} className={ui.muted}>
                {item.reason ?? item.fileName}
              </li>
            ))}
          </ul>
        </details>
      )}

      <div className={styles.actions}>
        {pending && (
          <button
            type="button"
            className={cx(ui.button, ui.primary)}
            onClick={onStart}
            disabled={starting}
          >
            {starting ? 'Iniciando…' : 'Sincronizar'}
          </button>
        )}
        <button type="button" className={ui.button} onClick={onDismiss} disabled={starting}>
          Fechar
        </button>
      </div>
    </div>
  )
}

function RunResult({ run }: { readonly run: SyncRun }) {
  if (run.running) {
    return (
      <p className={ui.alert} data-tone="info" role="status">
        Sincronizando… {run.done} de {run.total} (iniciada por {run.startedBy}). Pode sair da tela:
        ela continua no servidor.
      </p>
    )
  }

  const failed = run.failures.length
  return (
    <div className={styles.syncResult}>
      <p
        className={ui.alert}
        data-tone={run.error ? 'danger' : failed > 0 ? 'warning' : 'success'}
        role="status"
      >
        Última sincronização: {dateFormat.format(run.finishedAt ?? run.startedAt)}, por{' '}
        {run.startedBy}. {run.succeeded} ok
        {failed > 0 && `, ${String(failed)} com falha`}
        {run.total === 0 && ' (nada a fazer)'}.{run.error && ` Interrompida: ${run.error}`}
      </p>
      {failed > 0 && (
        <details>
          <summary>Ver falhas ({failed})</summary>
          <ul className={styles.uploads}>
            {run.failures.map((failure) => (
              <li key={`${failure.action}-${failure.fileName}`}>
                {failure.fileName}
                <span className={styles.reason}> — {failure.detail}</span>
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  )
}
