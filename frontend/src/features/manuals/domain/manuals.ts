export type ManualStatus = 'pending' | 'processing' | 'indexed' | 'failed'

export interface ManualSummary {
  readonly id: string
  readonly title: string
  readonly fileName: string
  readonly status: ManualStatus
  readonly pageCount: number | null
  readonly chunkCount: number | null
  /** Páginas com figuras descritas pela IA (fotos, desenhos, páginas escaneadas). */
  readonly figureCount: number | null
  /** As figuras estão sendo descritas agora, em segundo plano. */
  readonly describingFigures: boolean
  /** Páginas descritas no pedido atual (ou no último). */
  readonly figuresDescribed: number
  /** Por que a última descrição das figuras parou (o que já foi descrito fica guardado). */
  readonly figuresError: string | null
  readonly failureReason: string | null
  readonly createdAt: Date
}

/** Manual ainda sendo trabalhado no servidor: vale consultar de novo em instantes. */
export function isInProgress(manual: ManualSummary): boolean {
  return manual.status === 'pending' || manual.status === 'processing' || manual.describingFigures
}

/** Quantas páginas têm figuras e quantas ainda faltam descrever (cada uma é uma chamada à IA). */
export interface FigurePlan {
  readonly withFigures: number
  readonly pending: number
}

/** Escolha de quem importa: as figuras também vão para a IA? */
export interface FigureOption {
  readonly describeFigures: boolean
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
  /** As figuras dos manuais (re)indexados também vão para a IA. */
  readonly describeFigures: boolean
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

/** Sincronização automática, uma vez por dia, no horário da empresa. */
export interface SyncSchedule {
  readonly enabled: boolean
  /** "HH:MM" no fuso da empresa (``timezone``). */
  readonly time: string
  /** A sincronização agendada também descreve as figuras. */
  readonly describeFigures: boolean
  readonly timezone: string
  /** Próxima execução; nula quando desligada. */
  readonly nextRunAt: Date | null
  readonly lastTriggeredAt: Date | null
  /** Por que a última execução agendada não começou (ex.: pasta inacessível). */
  readonly lastTriggerError: string | null
  readonly updatedAt: Date | null
  readonly updatedBy: string | null
}

export interface SyncScheduleChange {
  readonly enabled: boolean
  readonly time: string
  readonly describeFigures: boolean
}

/** Sincronização com algo para fazer além de deixar como está. */
export function hasPendingChanges(check: SyncCheck): boolean {
  return check.items.some((item) => item.action !== 'ignore')
}

/** Porta: administração dos manuais, independente de transporte. */
export interface ManualsGateway {
  list(): Promise<ManualSummary[]>
  upload(file: File, option?: FigureOption): Promise<ManualSummary>
  reindex(id: string, option?: FigureOption): Promise<ManualSummary>
  /** Conta as páginas com figuras sem chamar a IA. */
  figurePlan(id: string): Promise<FigurePlan>
  /** Descreve as figuras de um manual já indexado, sem refazer o texto. */
  describeFigures(id: string): Promise<ManualSummary>
  remove(id: string): Promise<void>
  fileUrl(id: string): string
  syncStatus(): Promise<SyncStatus>
  checkSync(): Promise<SyncCheck>
  startSync(option?: FigureOption): Promise<SyncRun>
  syncSchedule(): Promise<SyncSchedule>
  updateSyncSchedule(change: SyncScheduleChange): Promise<SyncSchedule>
}
