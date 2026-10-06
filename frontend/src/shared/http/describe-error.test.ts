import { describe, expect, it } from 'vitest'

import { describeError } from './describe-error'
import { HttpError, InvalidResponseError, NetworkError, TimeoutError } from './errors'

describe('describeError', () => {
  it.each([
    [new NetworkError(), 'Não foi possível conectar ao servidor'],
    [new TimeoutError(1000), 'demorou demais'],
    [new HttpError(500, null), 'HTTP 500'],
    [new InvalidResponseError(), 'formato inesperado'],
    [new Error('boom'), 'erro inesperado'],
    ['não é um Error', 'erro inesperado'],
  ])('describes %o for the user', (error, expected) => {
    expect(describeError(error)).toContain(expected)
  })
})
