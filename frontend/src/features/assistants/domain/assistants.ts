// Mesmas regras da API (domain/assistant.py no backend, ADR 0013).
export const REQUEST_INSTRUCTIONS_MAX_LENGTH = 300

/** Os assistentes do chat. Um novo (ex.: o da TI) entra aqui e no backend. */
export type AssistantId = 'engenharia'

/** Quem usa o assistente quando o usuário não tem exceção. */
export type DefaultAccess = 'open' | 'restricted'

/** Exceção ao acesso padrão, para um usuário. */
export type UserAccess = 'granted' | 'denied'

/** Um assistente e se quem está usando pode conversar com ele. */
export interface AvailableAssistant {
  readonly id: AssistantId
  readonly name: string
  readonly topic: string
  readonly allowed: boolean
  /** Como pedir acesso, para quem não tem. */
  readonly requestInstructions: string
}

export interface AccessPolicy {
  readonly assistantId: AssistantId
  readonly name: string
  readonly defaultAccess: DefaultAccess
  /** null = mensagem padrão ("Peça o acesso a um administrador do sistema."). */
  readonly requestInstructions: string | null
  readonly updatedAt: Date | null
  readonly updatedBy: string | null
}

export interface AccessPolicyChanges {
  readonly defaultAccess: DefaultAccess
  readonly requestInstructions: string | null
}

export const DEFAULT_ACCESS_LABELS: Readonly<Record<DefaultAccess, string>> = {
  open: 'Liberado para todos',
  restricted: 'Só para quem for liberado',
}

/** Se um usuário que não é administrador usa o assistente: vale a exceção, senão o padrão. */
export function canUseAssistant(policy: AccessPolicy, access: UserAccess | undefined): boolean {
  if (access) return access === 'granted'
  return policy.defaultAccess === 'open'
}

/** Porta: os assistentes do chat e o acesso a cada um, independente de transporte. */
export interface AssistantsGateway {
  /** Os assistentes e se o usuário da sessão pode usar cada um. */
  mine(): Promise<AvailableAssistant[]>
  /** Acesso padrão de cada assistente (somente administradores). */
  policies(): Promise<AccessPolicy[]>
  updatePolicy(assistantId: AssistantId, changes: AccessPolicyChanges): Promise<AccessPolicy>
}
