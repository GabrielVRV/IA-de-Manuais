import { HttpError, NetworkError, TimeoutError } from './errors'

export interface HttpClientOptions {
  readonly timeoutMs?: number
  readonly fetchFn?: typeof fetch
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

  async getJson(path: string, signal?: AbortSignal): Promise<unknown> {
    const timeoutSignal = AbortSignal.timeout(this.#timeoutMs)
    const combinedSignal = signal ? AbortSignal.any([signal, timeoutSignal]) : timeoutSignal

    let response: Response
    try {
      response = await this.#fetch(`${this.#baseUrl}${path}`, {
        headers: { Accept: 'application/json' },
        signal: combinedSignal,
      })
    } catch (error) {
      // Cancelamento pedido por quem chamou não é falha: repassamos como veio.
      if (signal?.aborted) throw error
      if (timeoutSignal.aborted) throw new TimeoutError(this.#timeoutMs)
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
