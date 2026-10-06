/** A API respondeu, mas com status de erro (4xx/5xx). */
export class HttpError extends Error {
  override readonly name = 'HttpError'
  readonly status: number
  readonly body: unknown

  constructor(status: number, body: unknown) {
    super(`A API respondeu com HTTP ${String(status)}`)
    this.status = status
    this.body = body
  }
}

/** Não foi possível alcançar a API (servidor fora do ar, rede, CORS...). */
export class NetworkError extends Error {
  override readonly name = 'NetworkError'

  constructor(options?: ErrorOptions) {
    super('Não foi possível conectar à API', options)
  }
}

/** A API não respondeu dentro do tempo limite. */
export class TimeoutError extends Error {
  override readonly name = 'TimeoutError'

  constructor(timeoutMs: number) {
    super(`A API não respondeu em ${String(timeoutMs)} ms`)
  }
}

/** A API respondeu com um conteúdo fora do contrato esperado. */
export class InvalidResponseError extends Error {
  override readonly name = 'InvalidResponseError'

  constructor(options?: ErrorOptions) {
    super('A API retornou uma resposta em formato inesperado', options)
  }
}
