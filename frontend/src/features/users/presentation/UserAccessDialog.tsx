import { useEffect, useRef, useState } from 'react'

import {
  type AccessPolicy,
  canUseAssistant,
  DEFAULT_ACCESS_LABELS,
  type UserAccess,
} from '@/features/assistants/domain/assistants'
import { cx } from '@/shared/cx'
import ui from '@/styles/ui.module.css'

import type { AssistantAccessChange, ManagedUser } from '../domain/users'
import styles from './UserAccessDialog.module.css'

/** '' = seguir o acesso padrão do assistente. */
type Choice = UserAccess | ''

const CHOICES: readonly { value: Choice; label: string }[] = [
  { value: '', label: 'Seguir o padrão' },
  { value: 'granted', label: 'Liberado' },
  { value: 'denied', label: 'Bloqueado' },
]

/** Os acessos de um usuário a cada assistente do chat, salvos juntos. */
export function UserAccessDialog({
  user,
  policies,
  onSave,
  onClose,
}: {
  readonly user: ManagedUser
  readonly policies: readonly AccessPolicy[]
  /** Recebe só o que mudou; devolve se deu certo (o diálogo fecha). */
  readonly onSave: (changes: readonly AssistantAccessChange[]) => Promise<boolean>
  readonly onClose: () => void
}) {
  const dialogRef = useRef<HTMLDialogElement>(null)
  const [draft, setDraft] = useState<Partial<Record<string, Choice>>>(() => ({
    ...user.assistantAccess,
  }))
  const [saving, setSaving] = useState(false)
  const titleId = `user-access-${user.id}`

  // Modal nativo: prende o foco, fecha com Esc e escurece o fundo.
  useEffect(() => {
    const dialog = dialogRef.current
    if (!dialog) return
    if (typeof dialog.showModal === 'function') dialog.showModal()
    else dialog.setAttribute('open', '')
  }, [])

  const choiceFor = (policy: AccessPolicy): Choice => draft[policy.assistantId] ?? ''
  const changes = policies
    .filter((policy) => choiceFor(policy) !== (user.assistantAccess[policy.assistantId] ?? ''))
    .map((policy) => ({ assistantId: policy.assistantId, access: choiceFor(policy) || null }))

  return (
    <dialog
      ref={dialogRef}
      className={styles.dialog}
      aria-labelledby={titleId}
      onCancel={(event) => {
        event.preventDefault()
        onClose()
      }}
    >
      <form
        className={ui.stack}
        onSubmit={(event) => {
          event.preventDefault()
          setSaving(true)
          void onSave(changes).then((saved) => {
            setSaving(false)
            if (saved) onClose()
          })
        }}
      >
        <header>
          <h3 id={titleId} className={styles.title}>
            Acessos de {user.displayName}
          </h3>
          <p className={ui.hint}>
            Escolha, para cada assistente, se a pessoa segue o acesso padrão, fica liberada ou fica
            bloqueada.
          </p>
        </header>

        {policies.map((policy) => {
          const choice = choiceFor(policy)
          const allowed = canUseAssistant(policy, choice || undefined)
          return (
            <fieldset key={policy.assistantId} className={styles.assistant}>
              <legend className={styles.assistantName}>{policy.name}</legend>
              <p className={ui.hint}>
                Padrão do assistente: {DEFAULT_ACCESS_LABELS[policy.defaultAccess].toLowerCase()}
              </p>
              <div className={styles.choices}>
                {CHOICES.map((option) => (
                  <label
                    key={option.value}
                    className={styles.choice}
                    data-checked={choice === option.value}
                  >
                    <input
                      type="radio"
                      name={`${titleId}-${policy.assistantId}`}
                      value={option.value}
                      checked={choice === option.value}
                      onChange={() => {
                        setDraft((current) => ({ ...current, [policy.assistantId]: option.value }))
                      }}
                    />
                    {option.label}
                  </label>
                ))}
              </div>
              <p>
                <span className={ui.badge} data-tone={allowed ? 'success' : 'danger'}>
                  {allowed ? 'Usa este assistente' : 'Sem acesso'}
                </span>
              </p>
            </fieldset>
          )
        })}

        <div className={styles.actions}>
          <button type="button" className={ui.button} onClick={onClose}>
            Cancelar
          </button>
          <button
            type="submit"
            className={cx(ui.button, ui.primary)}
            disabled={saving || changes.length === 0}
          >
            {saving ? 'Salvando…' : 'Salvar acessos'}
          </button>
        </div>
      </form>
    </dialog>
  )
}
