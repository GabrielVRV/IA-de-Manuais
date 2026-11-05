import { useEffect, useState } from 'react'
import { Link } from 'react-router'

import { cx } from '@/shared/cx'
import { describeError } from '@/shared/http/describe-error'
import ui from '@/styles/ui.module.css'

import {
  type AccessPolicy,
  type AccessPolicyChanges,
  DEFAULT_ACCESS_LABELS,
  type DefaultAccess,
  REQUEST_INSTRUCTIONS_MAX_LENGTH,
} from '../domain/assistants'
import styles from './AccessAdmin.module.css'
import { useAssistantsGateway } from './assistants-gateway-context'

const dateFormat = new Intl.DateTimeFormat('pt-BR', { dateStyle: 'short', timeStyle: 'short' })

const ACCESS_HINTS: Readonly<Record<DefaultAccess, string>> = {
  open: 'Todo usuário ativo usa, inclusive quem entra pela primeira vez com o usuário de rede.',
  restricted: 'Só administradores e quem for liberado na tela de Usuários.',
}

/** Quem pode usar cada assistente do chat (ADR 0013). */
export function AccessAdmin() {
  const gateway = useAssistantsGateway()
  const [policies, setPolicies] = useState<AccessPolicy[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  // Carga inicial: o estado só muda nos callbacks da promessa, nunca no corpo do efeito.
  useEffect(() => {
    let active = true
    gateway.policies().then(
      (loaded) => {
        if (active) setPolicies(loaded)
      },
      (caught: unknown) => {
        if (active) setError(describeError(caught))
      },
    )
    return () => {
      active = false
    }
  }, [gateway])

  const save = async (policy: AccessPolicy, changes: AccessPolicyChanges) => {
    setError(null)
    setNotice(null)
    try {
      const saved = await gateway.updatePolicy(policy.assistantId, changes)
      // Por id: a lista mantém a ordem e troca só o assistente salvo.
      setPolicies((current) => [
        ...new Map((current ?? []).map((p) => [p.assistantId, p]))
          .set(saved.assistantId, saved)
          .values(),
      ])
      setNotice(`Acesso ao ${saved.name} salvo.`)
    } catch (caught) {
      setError(describeError(caught))
    }
  }

  return (
    <div className={ui.page}>
      <header className={ui.pageHeader}>
        <h2 className={ui.pageTitle}>Acessos</h2>
      </header>

      <div className={ui.stack}>
        <p className={ui.muted}>
          Defina quem usa cada assistente do chat. Para liberar ou bloquear uma pessoa fora do
          padrão, use a tela de <Link to="/admin/usuarios">Usuários</Link>. Administradores usam
          todos os assistentes.
        </p>
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
        {!policies && !error && <p className={ui.muted}>Carregando acessos…</p>}
        {policies?.map((policy) => (
          <PolicyForm
            // Recria o formulário quando a política salva muda.
            key={`${policy.assistantId}-${policy.updatedAt?.toISOString() ?? 'padrao'}`}
            policy={policy}
            onSave={(changes) => save(policy, changes)}
          />
        ))}
      </div>
    </div>
  )
}

function PolicyForm({
  policy,
  onSave,
}: {
  readonly policy: AccessPolicy
  readonly onSave: (changes: AccessPolicyChanges) => Promise<void>
}) {
  const [defaultAccess, setDefaultAccess] = useState(policy.defaultAccess)
  const [instructions, setInstructions] = useState(policy.requestInstructions ?? '')
  const [saving, setSaving] = useState(false)
  const titleId = `access-${policy.assistantId}`

  return (
    <form
      className={cx(ui.card, ui.stack)}
      aria-labelledby={titleId}
      onSubmit={(event) => {
        event.preventDefault()
        setSaving(true)
        void onSave({
          defaultAccess,
          requestInstructions: instructions.trim() || null,
        }).finally(() => {
          setSaving(false)
        })
      }}
    >
      <div className={styles.cardHeader}>
        <h3 id={titleId} className={styles.title}>
          {policy.name}
        </h3>
        {policy.updatedAt && (
          <span className={ui.hint}>
            Alterado por {policy.updatedBy ?? 'um administrador'} em{' '}
            {dateFormat.format(policy.updatedAt)}
          </span>
        )}
      </div>

      <fieldset className={styles.options}>
        <legend className={ui.label}>Acesso padrão</legend>
        {(['open', 'restricted'] as const).map((value) => (
          <label key={value} className={styles.option} data-checked={defaultAccess === value}>
            <input
              type="radio"
              name={`${titleId}-default`}
              value={value}
              checked={defaultAccess === value}
              onChange={() => {
                setDefaultAccess(value)
              }}
            />
            <span>
              <strong>{DEFAULT_ACCESS_LABELS[value]}</strong>
              <span className={ui.hint}>{ACCESS_HINTS[value]}</span>
            </span>
          </label>
        ))}
      </fieldset>

      <div className={ui.field}>
        <label className={ui.label} htmlFor={`${titleId}-instructions`}>
          Como pedir acesso
        </label>
        <textarea
          id={`${titleId}-instructions`}
          className={cx(ui.input, styles.instructions)}
          rows={2}
          maxLength={REQUEST_INSTRUCTIONS_MAX_LENGTH}
          placeholder="Peça o acesso a um administrador do sistema."
          aria-describedby={`${titleId}-instructions-hint`}
          value={instructions}
          onChange={(event) => {
            setInstructions(event.target.value)
          }}
        />
        <span id={`${titleId}-instructions-hint`} className={ui.hint}>
          Aparece para quem não tem acesso. Ex.: &quot;Abra um chamado no GLPI pedindo acesso ao{' '}
          {policy.name}.&quot; Em branco, vale a mensagem padrão.
        </span>
      </div>

      <div className={styles.actions}>
        <button type="submit" className={cx(ui.button, ui.primary)} disabled={saving}>
          {saving ? 'Salvando…' : 'Salvar acesso'}
        </button>
      </div>
    </form>
  )
}
