export type ManualStatus = 'pending' | 'processing' | 'indexed' | 'failed'

export interface ManualSummary {
  readonly id: string
  readonly title: string
  readonly fileName: string
  readonly status: ManualStatus
  readonly pageCount: number | null
  readonly chunkCount: number | null
  readonly failureReason: string | null
  readonly createdAt: Date
}

/** Manual ainda sendo trabalhado no servidor: vale consultar de novo em instantes. */
export function isInProgress(manual: ManualSummary): boolean {
  return manual.status === 'pending' || manual.status === 'processing'
}

/** O que a sincronização com a pasta da Engenharia faz com cada manual. */
export type SyncAction = 'add' | 'update' | 'retitle' | 'remove' | 'unchanged' | 'ignore'

export interface SyncPlanItem {
  readonly action: SyncAction
  readonly fileName: string
  readonly title: string
  /** Por que foi ignorado. */
  readonly reason: string | null
}

/** Resultado de "Verificar": o que a sincronização faria, sem ter alterado nada. */
export interface SyncCheck {
  readonly counts: Readonly<Record<SyncAction, number>>
  /** Quantos serão (re)indexados, ou seja, gastam API de IA. */
  readonly toIndex: number
  /** Tudo menos os que não mudaram. */
  readonly items: readonly SyncPlanItem[]
}

export interface SyncFailure {
  readonly action: SyncAction
  readonly fileName: string
  readonly detail: string
}

export interface SyncRun {
  readonly startedAt: Date
  readonly startedBy: string
  readonly finishedAt: Date | null
  readonly running: boolean
  readonly total: number
  readonly done: number
  readonly succeeded: number
  readonly failures: readonly SyncFailure[]
  /** Falha que interrompeu a sincronização inteira. */
  readonly error: string | null
}

export interface SyncStatus {
  /** Falso quando a pasta de manuais não está configurada no servidor. */
  readonly enabled: boolean
  readonly running: boolean
  /** A sincronização em andamento ou a última (some quando a API reinicia). */
  readonly lastRun: SyncRun | null
}

/** Sincronização com algo para fazer além de deixar como está. */
export function hasPendingChanges(check: SyncCheck): boolean {
  return check.items.some((item) => item.action !== 'ignore')
}

/** Porta: administração dos manuais, independente de transporte. */
export interface ManualsGateway {
  list(): Promise<ManualSummary[]>
  upload(file: File): Promise<ManualSummary>
  reindex(id: string): Promise<ManualSummary>
  remove(id: string): Promise<void>
  fileUrl(id: string): string
  syncStatus(): Promise<SyncStatus>
  checkSync(): Promise<SyncCheck>
  startSync(): Promise<SyncRun>
}
