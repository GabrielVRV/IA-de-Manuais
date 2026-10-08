import { HttpError, InvalidResponseError, NetworkError, TimeoutError } from './errors'

/** Converte qualquer erro em uma mensagem compreensível para o usuário final. */
export function describeError(error: unknown): string {
  if (error instanceof NetworkError) {
    return 'Não foi possível conectar ao servidor. Verifique se a API está no ar.'
  }
  if (error instanceof TimeoutError) {
    return 'O servidor demorou demais para responder. Tente novamente em instantes.'
  }
  if (error instanceof HttpError) {
    return describeHttpError(error)
  }
  if (error instanceof InvalidResponseError) {
    return 'O servidor respondeu em um formato inesperado.'
  }
  return 'Ocorreu um erro inesperado.'
}

function describeHttpError(error: HttpError): string {
  if (error.status === 503) {
    // O detalhe técnico (ex.: cota do provedor de IA) fica nos logs do servidor.
    return 'O assistente está temporariamente indisponível. Tente novamente em instantes.'
  }
  const detail = detailOf(error.body)
  // Erros 4xx da API trazem uma explicação pensada para o usuário (ex.: "arquivo não é PDF").
  if (detail && error.status >= 400 && error.status < 500) return detail
  return `O servidor respondeu com erro (HTTP ${String(error.status)}).`
}

function detailOf(body: unknown): string | null {
  if (typeof body === 'object' && body !== null && 'detail' in body) {
    const { detail } = body
    if (typeof detail === 'string') return detail
  }
  return null
}
