import { useEffect, useState } from 'react'
import { Link } from 'react-router'

import { cx } from '@/shared/cx'
import { describeError } from '@/shared/http/describe-error'
import ui from '@/styles/ui.module.css'

import {
  type DayUsage,
  USAGE_PERIODS,
  type UsagePeriod,
  type UsageReport as Report,
  type UsageTotals,
} from '../domain/usage'
import { formatUsd } from './format-usd'
import styles from './UsageReport.module.css'
import { useUsageGateway } from './usage-gateway-context'

const integer = new Intl.NumberFormat('pt-BR')
const dayLabel = new Intl.DateTimeFormat('pt-BR', {
  day: '2-digit',
  month: '2-digit',
  timeZone: 'UTC',
})

function formatDay(day: string): string {
  return dayLabel.format(new Date(`${day}T00:00:00Z`))
}

export function UsageReport() {
  const gateway = useUsageGateway()
  const [days, setDays] = useState<UsagePeriod>(30)
  const [report, setReport] = useState<{ days: UsagePeriod; data: Report } | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    gateway.report(days).then(
      (data) => {
        if (!active) return
        setReport({ days, data })
        setError(null)
      },
      (caught: unknown) => {
        if (active) setError(describeError(caught))
      },
    )
    return () => {
      active = false
    }
  }, [gateway, days])

  const data = report?.days === days ? report.data : null
  // Sem nenhum preço cadastrado, o custo seria sempre zero: melhor nem mostrar.
  const showCost = data?.byModel.some((m) => m.priced) ?? false

  return (
    <div className={ui.page}>
      <header className={ui.pageHeader}>
        <h2 className={ui.pageTitle}>Consumo</h2>
        <label className={styles.period}>
          <span className={ui.muted}>Período</span>
          <select
            className={ui.select}
            value={days}
            onChange={(event) => {
              setDays(Number(event.target.value) as UsagePeriod)
            }}
          >
            {USAGE_PERIODS.map((period) => (
              <option key={period} value={period}>
                Últimos {period} dias
              </option>
            ))}
          </select>
        </label>
      </header>

      <div className={ui.stack}>
        <p className={ui.hint}>
          Tokens gastos com o modelo de linguagem nas respostas do chat. Só números são registrados:
          as perguntas não aparecem aqui.
        </p>

        {error && (
          <p className={ui.alert} data-tone="danger" role="alert">
            {error}
          </p>
        )}

        {!data && !error && <p className={ui.muted}>Carregando consumo…</p>}

        {data && (
          <>
            {data.unpricedModels.length > 0 && (
              <p className={ui.alert} data-tone="warning" role="status">
                Sem preço cadastrado: <strong>{data.unpricedModels.join(', ')}</strong>.{' '}
                {showCost ? 'O custo abaixo não inclui esse consumo.' : 'O custo não é exibido.'}{' '}
                <Link to="/admin/configuracoes">Cadastrar o preço em Configurações</Link>.
              </p>
            )}

            <div className={styles.cards}>
              <Stat label="Perguntas" value={integer.format(data.totals.questions)} />
              <Stat
                label="Tokens"
                value={integer.format(data.totals.totalTokens)}
                detail={`${integer.format(data.totals.inputTokens)} de entrada · ${integer.format(data.totals.outputTokens)} de saída`}
              />
              {showCost && (
                <Stat
                  label="Custo estimado"
                  value={formatUsd(data.totals.costUsd)}
                  detail={data.totals.costIsPartial ? 'Incompleto: há modelo sem preço' : undefined}
                />
              )}
            </div>

            <section className={cx(ui.card, ui.stack)} aria-labelledby="usage-by-day">
              <h3 id="usage-by-day" className={styles.sectionTitle}>
                Tokens por dia
              </h3>
              <DailyChart days={data.byDay} />
            </section>

            <section className={ui.stack} aria-labelledby="usage-by-user">
              <h3 id="usage-by-user" className={styles.sectionTitle}>
                Quem mais usou
              </h3>
              {data.byUser.length === 0 ? (
                <p className={ui.muted}>Nenhuma pergunta no período.</p>
              ) : (
                <div className={styles.tableWrapper}>
                  <table className={styles.table} aria-label="Consumo por usuário">
                    <thead>
                      <tr>
                        <th>#</th>
                        <th>Nome</th>
                        <th>Login</th>
                        <th className={styles.number}>Perguntas</th>
                        <th className={styles.number}>Tokens</th>
                        {showCost && <th className={styles.number}>Custo</th>}
                      </tr>
                    </thead>
                    <tbody>
                      {data.byUser.map((user, index) => (
                        <tr key={user.userId}>
                          <td className={ui.muted}>{index + 1}</td>
                          <td>{user.displayName}</td>
                          <td className={ui.muted}>{user.username}</td>
                          <td className={styles.number}>{integer.format(user.totals.questions)}</td>
                          <td className={styles.number}>
                            {integer.format(user.totals.totalTokens)}
                          </td>
                          {showCost && <CostCell totals={user.totals} />}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>

            {data.byModel.length > 0 && (
              <section className={ui.stack} aria-labelledby="usage-by-model">
                <h3 id="usage-by-model" className={styles.sectionTitle}>
                  Por modelo
                </h3>
                <div className={styles.tableWrapper}>
                  <table className={styles.table} aria-label="Consumo por modelo">
                    <thead>
                      <tr>
                        <th>Modelo</th>
                        <th className={styles.number}>Perguntas</th>
                        <th className={styles.number}>Entrada</th>
                        <th className={styles.number}>Saída</th>
                        {showCost && <th className={styles.number}>Custo</th>}
                      </tr>
                    </thead>
                    <tbody>
                      {data.byModel.map((model) => (
                        <tr key={model.model}>
                          <td>
                            <span className={ui.code}>{model.model}</span>
                          </td>
                          <td className={styles.number}>
                            {integer.format(model.totals.questions)}
                          </td>
                          <td className={styles.number}>
                            {integer.format(model.totals.inputTokens)}
                          </td>
                          <td className={styles.number}>
                            {integer.format(model.totals.outputTokens)}
                          </td>
                          {showCost && <CostCell totals={model.totals} />}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            )}
          </>
        )}
      </div>
    </div>
  )
}

function Stat({
  label,
  value,
  detail,
}: {
  readonly label: string
  readonly value: string
  readonly detail?: string | undefined
}) {
  return (
    <div className={cx(ui.card, styles.stat)}>
      <span className={styles.statLabel}>{label}</span>
      <strong className={styles.statValue}>{value}</strong>
      {detail && <span className={ui.hint}>{detail}</span>}
    </div>
  )
}

function CostCell({ totals }: { readonly totals: UsageTotals }) {
  return (
    <td className={styles.number}>
      {formatUsd(totals.costUsd)}
      {totals.costIsPartial && (
        <span className={ui.muted} title="Inclui tokens de modelo sem preço cadastrado">
          {' '}
          *
        </span>
      )}
    </td>
  )
}

/** Barras simples: a altura é proporcional ao dia com mais tokens do período. */
function DailyChart({ days }: { readonly days: readonly DayUsage[] }) {
  const max = Math.max(1, ...days.map((d) => d.totals.totalTokens))
  const first = days[0]
  const last = days.at(-1)
  return (
    <figure className={styles.chart}>
      <div className={styles.bars} role="list" aria-label="Tokens por dia">
        {days.map((d) => {
          const label = `${formatDay(d.day)}: ${integer.format(d.totals.totalTokens)} tokens, ${integer.format(d.totals.questions)} pergunta(s)`
          return (
            <div
              key={d.day}
              className={styles.barSlot}
              role="listitem"
              aria-label={label}
              title={label}
            >
              <div
                className={styles.bar}
                style={{ height: `${String((d.totals.totalTokens / max) * 100)}%` }}
              />
            </div>
          )
        })}
      </div>
      {first && last && (
        <figcaption className={styles.axis}>
          <span>{formatDay(first.day)}</span>
          <span>Máximo: {integer.format(max)} tokens</span>
          <span>{formatDay(last.day)}</span>
        </figcaption>
      )}
    </figure>
  )
}
