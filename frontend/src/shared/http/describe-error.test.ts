import { describe, expect, it } from 'vitest'

import { describeError } from './describe-error'
import { HttpError, InvalidResponseError, NetworkError, TimeoutError } from './errors'

describe('describeError', () => {
  it.each([
    [new NetworkError(), 'Não foi possível conectar ao servidor'],
    [new TimeoutError(1000), 'demorou demais'],
    [new HttpError(500, null), 'HTTP 500'],
    [new HttpError(503, { detail: 'Cota do Gemini excedida' }), 'temporariamente indisponível'],
    [new HttpError(422, { detail: 'O arquivo enviado não é um PDF' }), 'não é um PDF'],
    [new HttpError(404, { detail: 42 }), 'HTTP 404'],
    [new InvalidResponseError(), 'formato inesperado'],
    [new Error('boom'), 'erro inesperado'],
    ['não é um Error', 'erro inesperado'],
  ])('describes %o for the user', (error, expected) => {
    expect(describeError(error)).toContain(expected)
  })
})
