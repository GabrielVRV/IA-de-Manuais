/** Configurações alteradas pelos administradores na tela, sem reiniciar a API. */
export interface SystemSettings {
  /** Meses que o consumo de cada usuário fica guardado. 0 = para sempre. */
  readonly usageRetentionMonths: number
  readonly updatedAt: Date | null
  readonly updatedBy: string | null
}

/** Só os campos informados mudam. */
export interface SettingsChanges {
  readonly usageRetentionMonths?: number
}

/** Um modelo já usado ou com preço cadastrado. Preços em dólares por milhão de tokens. */
export interface ModelPrice {
  readonly model: string
  readonly configured: boolean
  readonly inputPerMillion: number | null
  readonly outputPerMillion: number | null
}

export interface NewModelPrice {
  readonly model: string
  readonly inputPerMillion: number
  readonly outputPerMillion: number
}

export const USAGE_RETENTION_MAX_MONTHS = 120

/** Porta: configurações do sistema, independente de transporte. */
export interface SettingsGateway {
  get(): Promise<SystemSettings>
  update(changes: SettingsChanges): Promise<SystemSettings>
  listModelPrices(): Promise<ModelPrice[]>
  setModelPrice(price: NewModelPrice): Promise<ModelPrice>
  deleteModelPrice(model: string): Promise<void>
}
