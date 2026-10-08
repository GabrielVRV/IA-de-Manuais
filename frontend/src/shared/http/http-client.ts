import { HttpError, NetworkError, TimeoutError } from './errors'

export interface HttpClientOptions {
  readonly timeoutMs?: number
  readonly fetchFn?: typeof fetch
}

export interface RequestOptions {
  readonly signal?: AbortSignal | undefined
  /** Substitui o tempo limite padrão só nesta chamada. */
  readonly timeoutMs?: number
}

const DEFAULT_TIMEOUT_MS = 10_000

/** Cliente HTTP mínimo que traduz falhas de transporte em erros tipados. */
export class HttpClient {
  readonly #baseUrl: string
  readonly #timeoutMs: number
  readonly #fetch: typeof fetch

  constructor(baseUrl: string, options: HttpClientOptions = {}) {
    this.#baseUrl = baseUrl.replace(/\/+$/, '')
    this.#timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS
    this.#fetch = options.fetchFn ?? globalThis.fetch.bind(globalThis)
  }

  /** URL absoluta de um recurso da API (ex.: para links e downloads). */
  url(path: string): string {
    return `${this.#baseUrl}${path}`
  }

  getJson(path: string, options: RequestOptions = {}): Promise<unknown> {
    return this.#request(path, { method: 'GET', headers: { Accept: 'application/json' } }, options)
  }

  postJson(path: string, body: unknown, options: RequestOptions = {}): Promise<unknown> {
    return this.#request(
      path,
      {
        method: 'POST',
        body: JSON.stringify(body),
        headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
      },
      options,
    )
  }

  async #request(path: string, init: RequestInit, options: RequestOptions): Promise<unknown> {
    const timeoutMs = options.timeoutMs ?? this.#timeoutMs
    const timeoutSignal = AbortSignal.timeout(timeoutMs)
    const { signal } = options
    const combinedSignal = signal ? AbortSignal.any([signal, timeoutSignal]) : timeoutSignal

    let response: Response
    try {
      response = await this.#fetch(this.url(path), { ...init, signal: combinedSignal })
    } catch (error) {
      // Cancelamento pedido por quem chamou não é falha: repassamos como veio.
      if (signal?.aborted) throw error
      if (timeoutSignal.aborted) throw new TimeoutError(timeoutMs)
      throw new NetworkError({ cause: error })
    }

    const body = await readJsonBody(response)
    if (!response.ok) throw new HttpError(response.status, body)
    return body
  }
}

async function readJsonBody(response: Response): Promise<unknown> {
  try {
    return await response.json()
  } catch {
    return null
  }
}
