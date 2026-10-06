import { z } from 'zod'

/**
 * Configuração lida em tempo de execução de `config.json` (ao lado do index.html).
 * Assim o mesmo build serve para qualquer ambiente: basta editar o arquivo no XAMPP.
 */
export interface RuntimeConfig {
  readonly apiBaseUrl: string
}

const runtimeConfigSchema = z.object({
  apiBaseUrl: z.url({ protocol: /^https?$/ }),
})

export class RuntimeConfigError extends Error {
  override readonly name = 'RuntimeConfigError'
}

export function parseRuntimeConfig(raw: unknown): RuntimeConfig {
  const result = runtimeConfigSchema.safeParse(raw)
  if (!result.success) {
    throw new RuntimeConfigError(
      'config.json inválido: "apiBaseUrl" deve ser uma URL http(s), ex.: "http://servidor:8000".',
      { cause: result.error },
    )
  }
  return { apiBaseUrl: result.data.apiBaseUrl.replace(/\/+$/, '') }
}

export async function loadRuntimeConfig(
  url = './config.json',
  fetchFn: typeof fetch = globalThis.fetch.bind(globalThis),
): Promise<RuntimeConfig> {
  let response: Response
  try {
    // no-store: uma alteração no config.json vale já no próximo carregamento da página.
    response = await fetchFn(url, { cache: 'no-store' })
  } catch (error) {
    throw new RuntimeConfigError('Não foi possível carregar o config.json.', { cause: error })
  }
  if (!response.ok) {
    throw new RuntimeConfigError(
      `Não foi possível carregar o config.json (HTTP ${String(response.status)}).`,
    )
  }

  let raw: unknown
  try {
    raw = await response.json()
  } catch (error) {
    throw new RuntimeConfigError('config.json não contém um JSON válido.', { cause: error })
  }
  return parseRuntimeConfig(raw)
}
