import { useEffect, useRef, useState } from 'react'
import { Link, NavLink } from 'react-router'

import { cx } from '@/shared/cx'
import { describeError } from '@/shared/http/describe-error'

import {
  type ConversationSummary,
  groupByRecency,
  isValidTitle,
  TITLE_MAX_LENGTH,
} from '../domain/chat'
import styles from './HistorySidebar.module.css'
import { Icon } from './Message'
import type { ConversationsState } from './use-conversations'

interface HistorySidebarProps {
  readonly history: ConversationsState
  readonly activeId: string | null
  /** Gaveta aberta (telas pequenas); no computador a barra fica sempre visível. */
  readonly open: boolean
  readonly onClose: () => void
  /** A conversa aberta foi apagada: volta para uma conversa nova. */
  readonly onActiveDeleted: () => void
}

/** Busca sem diferenciar maiúsculas nem acentos: "oleo" acha "Óleo". */
function normalize(text: string): string {
  return text
    .normalize('NFD')
    .replace(/\p{Diacritic}/gu, '')
    .toLowerCase()
}

export function HistorySidebar({
  history,
  activeId,
  open,
  onClose,
  onActiveDeleted,
}: HistorySidebarProps) {
  const { conversations, error } = history
  const [query, setQuery] = useState('')

  const filtered =
    conversations?.filter((c) => normalize(c.title).includes(normalize(query.trim()))) ?? []
  const groups = groupByRecency(filtered, new Date())

  return (
    <>
      <div
        className={cx(styles.scrim, open && styles.scrimVisible)}
        onClick={onClose}
        aria-hidden="true"
      />
      <aside
        className={cx(styles.sidebar, open && styles.open)}
        aria-label="Histórico de conversas"
      >
        <div className={styles.head}>
          <Link to="/" className={styles.newChat} onClick={onClose}>
            <Icon d="M8 3v10M3 8h10" />
            Nova conversa
          </Link>
          <button
            type="button"
            className={styles.close}
            onClick={onClose}
            aria-label="Fechar o histórico"
          >
            <Icon d="M4 4l8 8M12 4l-8 8" />
          </button>
        </div>

        <label className={styles.search}>
          <Icon d="M7 12.5a5.5 5.5 0 1 1 0-11 5.5 5.5 0 0 1 0 11zM11 11l3.5 3.5" />
          <span className={styles.visuallyHidden}>Buscar no histórico</span>
          <input
            type="search"
            value={query}
            onChange={(event) => {
              setQuery(event.target.value)
            }}
            placeholder="Buscar conversas"
          />
        </label>

        <nav className={styles.list} aria-label="Conversas anteriores">
          {conversations === null && !error && <SkeletonList />}
          {error && <p className={styles.message}>{error}</p>}
          {conversations?.length === 0 && (
            <p className={styles.message}>
              Suas conversas aparecem aqui. Elas ficam guardadas só para você.
            </p>
          )}
          {conversations && conversations.length > 0 && filtered.length === 0 && (
            <p className={styles.message}>Nenhuma conversa com “{query.trim()}”.</p>
          )}
          {groups.map((group) => (
            <section key={group.label} className={styles.group}>
              <h3 className={styles.groupLabel}>{group.label}</h3>
              <ul>
                {group.conversations.map((conversation) => (
                  <HistoryItem
                    key={conversation.id}
                    conversation={conversation}
                    active={conversation.id === activeId}
                    history={history}
                    onNavigate={onClose}
                    onDeleted={() => {
                      if (conversation.id === activeId) onActiveDeleted()
                    }}
                  />
                ))}
              </ul>
            </section>
          ))}
        </nav>
      </aside>
    </>
  )
}

type Mode = 'view' | 'rename' | 'confirm-delete'

function HistoryItem({
  conversation,
  active,
  history,
  onNavigate,
  onDeleted,
}: {
  readonly conversation: ConversationSummary
  readonly active: boolean
  readonly history: ConversationsState
  readonly onNavigate: () => void
  readonly onDeleted: () => void
}) {
  const [mode, setMode] = useState<Mode>('view')
  const [title, setTitle] = useState(conversation.title)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (mode === 'rename') inputRef.current?.select()
  }, [mode])

  const cancel = () => {
    setMode('view')
    setTitle(conversation.title)
    setError(null)
  }

  const run = async (action: () => Promise<void>) => {
    setBusy(true)
    setError(null)
    try {
      await action()
      setMode('view')
    } catch (caught) {
      setError(describeError(caught))
    } finally {
      setBusy(false)
    }
  }

  if (mode === 'rename') {
    return (
      <li className={cx(styles.item, active && styles.active)}>
        <form
          className={styles.renameForm}
          onSubmit={(event) => {
            event.preventDefault()
            if (!isValidTitle(title) || title.trim() === conversation.title) {
              cancel()
              return
            }
            void run(() => history.rename(conversation.id, title))
          }}
        >
          <input
            ref={inputRef}
            aria-label="Novo título da conversa"
            value={title}
            maxLength={TITLE_MAX_LENGTH}
            disabled={busy}
            onChange={(event) => {
              setTitle(event.target.value)
            }}
            onKeyDown={(event) => {
              if (event.key === 'Escape') cancel()
            }}
          />
          <button type="submit" className={styles.miniButton} disabled={busy} aria-label="Salvar">
            <Icon d="M3 8.5l3 3 7-7" />
          </button>
        </form>
        {error && <p className={styles.itemError}>{error}</p>}
      </li>
    )
  }

  return (
    <li className={cx(styles.item, active && styles.active)}>
      <NavLink
        to={`/c/${encodeURIComponent(conversation.id)}`}
        className={styles.link}
        onClick={onNavigate}
        aria-current={active ? 'page' : undefined}
        title={conversation.title}
      >
        {conversation.title}
      </NavLink>
      {mode === 'view' ? (
        <div className={styles.actions}>
          <button
            type="button"
            className={styles.miniButton}
            onClick={() => {
              setMode('rename')
            }}
            aria-label={`Renomear “${conversation.title}”`}
            title="Renomear"
          >
            <Icon d="M10.5 2.5l3 3-8 8h-3v-3z" />
          </button>
          <button
            type="button"
            className={cx(styles.miniButton, styles.danger)}
            onClick={() => {
              setMode('confirm-delete')
            }}
            aria-label={`Apagar “${conversation.title}”`}
            title="Apagar"
          >
            <Icon d="M3 4.5h10M6.5 4.5V3h3v1.5M4.5 4.5l.7 9h5.6l.7-9" />
          </button>
        </div>
      ) : (
        <div className={styles.confirm} role="group" aria-label="Confirmar exclusão">
          <span>Apagar esta conversa?</span>
          <button
            type="button"
            className={cx(styles.confirmButton, styles.danger)}
            disabled={busy}
            onClick={() => {
              void run(async () => {
                await history.remove(conversation.id)
                onDeleted()
              })
            }}
          >
            Apagar
          </button>
          <button type="button" className={styles.confirmButton} onClick={cancel} disabled={busy}>
            Cancelar
          </button>
        </div>
      )}
      {error && <p className={styles.itemError}>{error}</p>}
    </li>
  )
}

function SkeletonList() {
  return (
    <div className={styles.skeleton} aria-hidden="true">
      {[78, 62, 85, 54, 70].map((width) => (
        <span key={width} style={{ width: `${String(width)}%` }} />
      ))}
    </div>
  )
}
