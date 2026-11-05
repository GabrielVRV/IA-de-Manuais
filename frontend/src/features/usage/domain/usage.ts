/** Quanto foi gasto do modelo de linguagem. Só números: nenhuma pergunta aparece aqui. */
export interface UsageTotals {
  readonly questions: number
  readonly inputTokens: number
  readonly outputTokens: number
  readonly totalTokens: number
  /** Em dólares, só dos modelos com preço cadastrado. */
  readonly costUsd: number
  /** Houve tokens de algum modelo sem preço: o custo está subestimado. */
  readonly costIsPartial: boolean
}

export interface DayUsage {
  /** Dia no fuso da empresa, como "AAAA-MM-DD". */
  readonly day: string
  readonly totals: UsageTotals
}

export interface UserUsage {
  readonly userId: string
  readonly username: string
  readonly displayName: string
  readonly totals: UsageTotals
}

export interface ModelUsage {
  readonly model: string
  readonly priced: boolean
  readonly totals: UsageTotals
}

export interface UsageReport {
  readonly firstDay: string
  readonly lastDay: string
  readonly timezone: string
  readonly totals: UsageTotals
  readonly byDay: readonly DayUsage[]
  /** De quem mais gastou tokens para quem menos gastou. */
  readonly byUser: readonly UserUsage[]
  readonly byModel: readonly ModelUsage[]
  readonly unpricedModels: readonly string[]
}

export const USAGE_PERIODS = [7, 30, 90] as const
export type UsagePeriod = (typeof USAGE_PERIODS)[number]

/** Porta: relatório de consumo, independente de transporte. */
export interface UsageGateway {
  report(days: UsagePeriod): Promise<UsageReport>
}
