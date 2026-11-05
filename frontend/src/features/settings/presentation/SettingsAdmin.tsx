import { useCallback, useEffect, useState } from 'react'

import { cx } from '@/shared/cx'
import { describeError } from '@/shared/http/describe-error'
import ui from '@/styles/ui.module.css'

import {
  type ModelPrice,
  QUESTION_LIMIT_MAX,
  type SystemSettings,
  USAGE_RETENTION_MAX_MONTHS,
} from '../domain/settings'
import { parsePrice, priceText } from './price-text'
import styles from './SettingsAdmin.module.css'
import { useSettingsGateway } from './settings-gateway-context'

const dateFormat = new Intl.DateTimeFormat('pt-BR', { dateStyle: 'short', timeStyle: 'short' })

export function SettingsAdmin() {
  const gateway = useSettingsGateway()
  const [settings, setSettings] = useState<SystemSettings | null>(null)
  const [prices, setPrices] = useState<ModelPrice[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  const refreshPrices = useCallback(async () => {
    setPrices(await gateway.listModelPrices())
  }, [gateway])

  // Carga inicial: o estado só muda nos callbacks da promessa, nunca no corpo do efeito.
  useEffect(() => {
    let active = true
    Promise.all([gateway.get(), gateway.listModelPrices()]).then(
      ([loaded, list]) => {
        if (!active) return
        setSettings(loaded)
        setPrices(list)
      },
      (caught: unknown) => {
        if (active) setError(describeError(caught))
      },
    )
    return () => {
      active = false
    }
  }, [gateway])

  const run = async (action: () => Promise<unknown>, success: string) => {
    setError(null)
    setNotice(null)
    try {
      await action()
      setNotice(success)
      return true
    } catch (caught) {
      setError(describeError(caught))
      return false
    }
  }

  return (
    <div className={ui.page}>
      <header className={ui.pageHeader}>
        <h2 className={ui.pageTitle}>Configurações</h2>
        {settings?.updatedAt && (
          <span className={ui.muted}>
            Alterado por {settings.updatedBy ?? 'um administrador'} em{' '}
            {dateFormat.format(settings.updatedAt)}
          </span>
        )}
      </header>

      <div className={ui.stack}>
        {error && (
          <p className={ui.alert} data-tone="danger" role="alert">
            {error}
          </p>
        )}
        {notice && (
          <p className={ui.alert} data-tone="success" role="status">
            {notice}
          </p>
        )}

        {!settings && !error && <p className={ui.muted}>Carregando configurações…</p>}

        {settings && (
          <QuestionLimitsForm
            settings={settings}
            onSave={(changes) =>
              run(async () => {
                setSettings(await gateway.update(changes))
              }, 'Limites de perguntas salvos.')
            }
          />
        )}

        {settings && (
          <RetentionForm
            settings={settings}
            onSave={(months) =>
              run(async () => {
                setSettings(await gateway.update({ usageRetentionMonths: months }))
              }, 'Retenção do consumo salva.')
            }
          />
        )}

        {prices && (
          <section className={cx(ui.card, ui.stack)} aria-labelledby="model-prices">
            <h3 id="model-prices" className={styles.sectionTitle}>
              Preço dos modelos
            </h3>
            <span className={ui.hint}>
              Em dólares por milhão de tokens, como na tabela de preços do provedor. Usado só para
              estimar o custo na tela de Consumo. Modelos já usados aparecem aqui mesmo sem preço.
            </span>
            {prices.length > 0 && (
              <div className={styles.tableWrapper}>
                <table className={styles.table}>
                  <thead>
                    <tr>
                      <th>Modelo</th>
                      <th>Entrada (US$/milhão)</th>
                      <th>Saída (US$/milhão)</th>
                      <th>
                        <span className={ui.visuallyHidden}>Ações</span>
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {prices.map((price) => (
                      <PriceRow
                        key={price.model}
                        price={price}
                        onSave={(inputPerMillion, outputPerMillion) =>
                          run(async () => {
                            await gateway.setModelPrice({
                              model: price.model,
                              inputPerMillion,
                              outputPerMillion,
                            })
                            await refreshPrices()
                          }, `Preço de ${price.model} salvo.`)
                        }
                        onRemove={() => {
                          if (!window.confirm(`Remover o preço de ${price.model}?`)) return
                          void run(async () => {
                            await gateway.deleteModelPrice(price.model)
                            await refreshPrices()
                          }, `Preço de ${price.model} removido.`)
                        }}
                      />
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <NewPriceForm
              onSave={(model, inputPerMillion, outputPerMillion) =>
                run(async () => {
                  await gateway.setModelPrice({ model, inputPerMillion, outputPerMillion })
                  await refreshPrices()
                }, `Preço de ${model} salvo.`)
              }
            />
          </section>
        )}
      </div>
    </div>
  )
}

/** Inteiro de 0 a ``max`` digitado num campo; null quando inválido. */
function wholeNumber(text: string, max: number): number | null {
  if (!/^\d+$/.test(text.trim())) return null
  const value = Number(text)
  return value <= max ? value : null
}

function QuestionLimitsForm({
  settings,
  onSave,
}: {
  readonly settings: SystemSettings
  readonly onSave: (changes: {
    questionsPerMinute: number
    questionsPerDay: number
  }) => Promise<boolean>
}) {
  const [perMinute, setPerMinute] = useState(String(settings.questionsPerMinute))
  const [perDay, setPerDay] = useState(String(settings.questionsPerDay))
  const [saving, setSaving] = useState(false)
  const minuteValue = wholeNumber(perMinute, QUESTION_LIMIT_MAX)
  const dayValue = wholeNumber(perDay, QUESTION_LIMIT_MAX)

  return (
    <form
      className={cx(ui.card, ui.stack)}
      aria-labelledby="question-limits"
      onSubmit={(event) => {
        event.preventDefault()
        if (minuteValue === null || dayValue === null) return
        setSaving(true)
        void onSave({ questionsPerMinute: minuteValue, questionsPerDay: dayValue }).finally(() => {
          setSaving(false)
        })
      }}
    >
      <h3 id="question-limits" className={styles.sectionTitle}>
        Limite de perguntas
      </h3>
      <span className={ui.hint}>
        Quantas perguntas cada usuário pode fazer, para proteger a cota da API de IA (vale também
        para administradores). Acima do limite, o chat avisa e a pergunta não é enviada ao modelo.
        Use 0 para não limitar.
      </span>
      <div className={ui.row}>
        <label className={ui.field}>
          <span className={ui.label}>Por minuto</span>
          <input
            className={ui.input}
            type="number"
            min={0}
            max={QUESTION_LIMIT_MAX}
            step={1}
            value={perMinute}
            onChange={(e) => {
              setPerMinute(e.target.value)
            }}
            required
          />
        </label>
        <label className={ui.field}>
          <span className={ui.label}>Em 24 horas</span>
          <input
            className={ui.input}
            type="number"
            min={0}
            max={QUESTION_LIMIT_MAX}
            step={1}
            value={perDay}
            onChange={(e) => {
              setPerDay(e.target.value)
            }}
            required
          />
        </label>
        <button
          type="submit"
          className={cx(ui.button, ui.primary)}
          disabled={minuteValue === null || dayValue === null || saving}
        >
          {saving ? 'Salvando…' : 'Salvar limites'}
        </button>
      </div>
    </form>
  )
}

function RetentionForm({
  settings,
  onSave,
}: {
  readonly settings: SystemSettings
  readonly onSave: (months: number) => Promise<boolean>
}) {
  const [months, setMonths] = useState(String(settings.usageRetentionMonths))
  const [saving, setSaving] = useState(false)
  const value = wholeNumber(months, USAGE_RETENTION_MAX_MONTHS)

  return (
    <form
      className={cx(ui.card, ui.stack)}
      aria-labelledby="usage-retention"
      onSubmit={(event) => {
        event.preventDefault()
        if (value === null) return
        setSaving(true)
        void onSave(value).finally(() => {
          setSaving(false)
        })
      }}
    >
      <h3 id="usage-retention" className={styles.sectionTitle}>
        Retenção do consumo
      </h3>
      <span className={ui.hint}>
        Por quanto tempo o consumo de cada usuário (data, modelo e tokens) fica guardado. Depois
        disso é apagado automaticamente. Use 0 para guardar para sempre.
      </span>
      <div className={ui.row}>
        <label className={ui.field}>
          <span className={ui.label}>Meses</span>
          <input
            className={ui.input}
            type="number"
            min={0}
            max={USAGE_RETENTION_MAX_MONTHS}
            step={1}
            value={months}
            onChange={(e) => {
              setMonths(e.target.value)
            }}
            required
          />
        </label>
        <button
          type="submit"
          className={cx(ui.button, ui.primary)}
          disabled={value === null || saving}
        >
          {saving ? 'Salvando…' : 'Salvar retenção'}
        </button>
      </div>
    </form>
  )
}

function PriceRow({
  price,
  onSave,
  onRemove,
}: {
  readonly price: ModelPrice
  readonly onSave: (inputPerMillion: number, outputPerMillion: number) => Promise<boolean>
  readonly onRemove: () => void
}) {
  const [input, setInput] = useState(priceText(price.inputPerMillion))
  const [output, setOutput] = useState(priceText(price.outputPerMillion))
  const inputValue = parsePrice(input)
  const outputValue = parsePrice(output)

  return (
    <tr>
      <td>
        <span className={ui.code}>{price.model}</span>{' '}
        {!price.configured && (
          <span className={ui.badge} data-tone="warning">
            Sem preço
          </span>
        )}
      </td>
      <td>
        <input
          className={cx(ui.input, styles.priceInput)}
          inputMode="decimal"
          aria-label={`Preço de entrada de ${price.model}`}
          value={input}
          onChange={(e) => {
            setInput(e.target.value)
          }}
        />
      </td>
      <td>
        <input
          className={cx(ui.input, styles.priceInput)}
          inputMode="decimal"
          aria-label={`Preço de saída de ${price.model}`}
          value={output}
          onChange={(e) => {
            setOutput(e.target.value)
          }}
        />
      </td>
      <td>
        <div className={styles.actions}>
          <button
            type="button"
            className={cx(ui.button, ui.primary)}
            disabled={inputValue === null || outputValue === null}
            aria-label={`Salvar o preço de ${price.model}`}
            onClick={() => {
              if (inputValue !== null && outputValue !== null) void onSave(inputValue, outputValue)
            }}
          >
            Salvar
          </button>
          {price.configured && (
            <button
              type="button"
              className={cx(ui.button, ui.danger)}
              aria-label={`Remover o preço de ${price.model}`}
              onClick={onRemove}
            >
              Remover
            </button>
          )}
        </div>
      </td>
    </tr>
  )
}

function NewPriceForm({
  onSave,
}: {
  readonly onSave: (
    model: string,
    inputPerMillion: number,
    outputPerMillion: number,
  ) => Promise<boolean>
}) {
  const [model, setModel] = useState('')
  const [input, setInput] = useState('')
  const [output, setOutput] = useState('')
  const inputValue = parsePrice(input)
  const outputValue = parsePrice(output)
  const valid = model.trim() !== '' && inputValue !== null && outputValue !== null

  return (
    <form
      className={ui.row}
      aria-label="Cadastrar preço de outro modelo"
      onSubmit={(event) => {
        event.preventDefault()
        if (inputValue === null || outputValue === null) return
        void onSave(model.trim(), inputValue, outputValue).then((saved) => {
          if (!saved) return
          setModel('')
          setInput('')
          setOutput('')
        })
      }}
    >
      <label className={cx(ui.field, ui.grow)}>
        <span className={ui.label}>Outro modelo</span>
        <input
          className={ui.input}
          value={model}
          placeholder="gpt-4.1-mini"
          spellCheck={false}
          autoCapitalize="none"
          onChange={(e) => {
            setModel(e.target.value)
          }}
        />
      </label>
      <label className={ui.field}>
        <span className={ui.label}>Entrada (US$/milhão)</span>
        <input
          className={cx(ui.input, styles.priceInput)}
          inputMode="decimal"
          value={input}
          onChange={(e) => {
            setInput(e.target.value)
          }}
        />
      </label>
      <label className={ui.field}>
        <span className={ui.label}>Saída (US$/milhão)</span>
        <input
          className={cx(ui.input, styles.priceInput)}
          inputMode="decimal"
          value={output}
          onChange={(e) => {
            setOutput(e.target.value)
          }}
        />
      </label>
      <button type="submit" className={ui.button} disabled={!valid}>
        Adicionar
      </button>
    </form>
  )
}
