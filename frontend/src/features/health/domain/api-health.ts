export type ServiceStatus = 'up' | 'down'

export interface ApiHealth {
  readonly status: ServiceStatus
  readonly version: string
  readonly components: Readonly<Record<string, ServiceStatus>>
}

/** Porta: como a aplicação obtém a saúde da API, independente de transporte. */
export interface HealthGateway {
  check(signal?: AbortSignal): Promise<ApiHealth>
}
