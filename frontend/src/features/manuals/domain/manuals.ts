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

/** Porta: administração dos manuais, independente de transporte. */
export interface ManualsGateway {
  list(): Promise<ManualSummary[]>
  upload(file: File): Promise<ManualSummary>
  reindex(id: string): Promise<ManualSummary>
  remove(id: string): Promise<void>
  fileUrl(id: string): string
}
