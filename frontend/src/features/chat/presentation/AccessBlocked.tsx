import type { AvailableAssistant } from '@/features/assistants/domain/assistants'
import { VisorBot } from '@/shared/mascot/VisorBot'

import styles from './AccessBlocked.module.css'

/** No lugar do chat, para quem não tem acesso ao assistente: diz como pedir. */
export function AccessBlocked({ assistant }: { readonly assistant: AvailableAssistant }) {
  return (
    <section className={styles.blocked} aria-labelledby="access-blocked-title">
      <VisorBot mood="happy" className={styles.bot} />
      <p className={styles.badge}>{assistant.name}</p>
      <h2 id="access-blocked-title" className={styles.title}>
        Você ainda não tem acesso a este assistente
      </h2>
      <p className={styles.instructions}>{assistant.requestInstructions}</p>
    </section>
  )
}
