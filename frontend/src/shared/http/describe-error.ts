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
    return `O servidor respondeu com erro (HTTP ${String(error.status)}).`
  }
  if (error instanceof InvalidResponseError) {
    return 'O servidor respondeu em um formato inesperado.'
  }
  return 'Ocorreu um erro inesperado.'
}
