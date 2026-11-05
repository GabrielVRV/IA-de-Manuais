import { useEffect, useState } from 'react'

import { cx } from '@/shared/cx'
import { describeError } from '@/shared/http/describe-error'
import ui from '@/styles/ui.module.css'

import type { SyncSchedule } from '../domain/manuals'
import styles from './ManualsAdmin.module.css'
import { useManualsGateway } from './manuals-gateway-context'

const TIME_PATTERN = /^([01]\d|2[0-3]):[0-5]\d$/

/** Data e hora no relógio da empresa (o mesmo do agendamento), não no do navegador. */
function formatAt(date: Date, timezone: string): string {
  return new Intl.DateTimeFormat('pt-BR', {
    dateStyle: 'short',
    timeStyle: 'short',
    timeZone: timezone,
  }).format(date)
}

/** Liga, desliga e escolhe o horário da sincronização diária com a pasta da Engenharia. */
export function SyncScheduleForm() {
  const gateway = useManualsGateway()
  const [schedule, setSchedule] = useState<SyncSchedule | null>(null)
  const [enabled, setEnabled] = useState(false)
  const [time, setTime] = useState('00:00')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)

  const show = (loaded: SyncSchedule) => {
    setSchedule(loaded)
    setEnabled(loaded.enabled)
    setTime(loaded.time)
  }

  // Carga inicial: o estado só muda nos callbacks da promessa, nunca no corpo do efeito.
  useEffect(() => {
    let active = true
    gateway.syncSchedule().then(
      (loaded) => {
        if (active) show(loaded)
      },
      (caught: unknown) => {
        if (active) setError(describeError(caught))
      },
    )
    return () => {
      active = false
    }
  }, [gateway])

  if (!schedule) {
    return error ? (
      <p className={ui.alert} data-tone="danger" role="alert">
        {error}
      </p>
    ) : null
  }

  const validTime = TIME_PATTERN.test(time)
  const changed = enabled !== schedule.enabled || time !== schedule.time

  const save = async () => {
    setSaving(true)
    setError(null)
    setSaved(false)
    try {
      show(await gateway.updateSyncSchedule({ enabled, time }))
      setSaved(true)
    } catch (caught) {
      setError(describeError(caught))
    } finally {
      setSaving(false)
    }
  }

  return (
    <form
      className={cx(ui.stack, styles.schedule)}
      aria-label="Sincronização automática"
      onSubmit={(event) => {
        event.preventDefault()
        void save()
      }}
    >
      <div className={cx(ui.row, styles.scheduleRow)}>
        <label className={styles.checkbox}>
          <input
            type="checkbox"
            checked={enabled}
            onChange={(e) => {
              setEnabled(e.target.checked)
              setSaved(false)
            }}
          />
          Sincronizar automaticamente todo dia às
        </label>
        <input
          className={cx(ui.input, styles.timeInput)}
          type="time"
          aria-label="Horário da sincronização"
          value={time}
          required
          onChange={(e) => {
            setTime(e.target.value)
            setSaved(false)
          }}
        />
        <button
          type="submit"
          className={cx(ui.button, ui.primary)}
          disabled={!changed || !validTime || saving}
        >
          {saving ? 'Salvando…' : 'Salvar agendamento'}
        </button>
      </div>

      <span className={ui.hint}>
        Horário de {schedule.timezone}. Faz o mesmo que o botão Sincronizar e gasta API de IA só com
        manuais novos ou alterados. Se o servidor estiver desligado no horário, roda quando ele
        voltar.
      </span>

      {schedule.enabled && schedule.nextRunAt && (
        <span className={ui.muted} role="status">
          {saved ? 'Agendamento salvo. ' : ''}Próxima sincronização:{' '}
          {formatAt(schedule.nextRunAt, schedule.timezone)}.
        </span>
      )}
      {!schedule.enabled && saved && (
        <span className={ui.muted} role="status">
          Sincronização automática desligada.
        </span>
      )}

      {schedule.lastTriggerError && schedule.lastTriggeredAt && (
        <p className={ui.alert} data-tone="warning">
          A sincronização agendada de {formatAt(schedule.lastTriggeredAt, schedule.timezone)} não
          começou: {schedule.lastTriggerError}
        </p>
      )}

      {error && (
        <p className={ui.alert} data-tone="danger" role="alert">
          {error}
        </p>
      )}
    </form>
  )
}
