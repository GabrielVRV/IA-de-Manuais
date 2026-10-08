import { describe, expect, it, vi } from 'vitest'

import { InvalidResponseError } from '@/shared/http/errors'
import { HttpClient } from '@/shared/http/http-client'

import { HttpQuestionGateway, QUESTION_TIMEOUT_MS } from './http-question-gateway'

const apiAnswer = {
  answer: 'A pressão máxima é **10 bar**.',
  found: true,
  citations: [
    {
      manual_id: 'abc-123',
      manual_title: 'Compressor CX-500',
      pages: [3, 4],
      pages_label: 'p. 3-4',
    },
  ],
}

function gatewayReturning(body: unknown) {
  const fetchFn = vi.fn<typeof fetch>().mockResolvedValue(Response.json(body))
  const http = new HttpClient('http://api.local', { fetchFn })
  return { gateway: new HttpQuestionGateway(http), fetchFn, http }
}

describe('HttpQuestionGateway', () => {
  it('posts the question and maps the answer', async () => {
    const { gateway, fetchFn } = gatewayReturning(apiAnswer)

    const answer = await gateway.ask('Qual a pressão?')

    expect(answer).toEqual({
      text: 'A pressão máxima é **10 bar**.',
      found: true,
      citations: [
        {
          manualId: 'abc-123',
          manualTitle: 'Compressor CX-500',
          pages: [3, 4],
          pagesLabel: 'p. 3-4',
        },
      ],
    })
    expect(fetchFn).toHaveBeenCalledWith(
      'http://api.local/api/v1/questions',
      expect.objectContaining({ method: 'POST', body: '{"question":"Qual a pressão?"}' }),
    )
  })

  it('uses a long timeout, since the AI provider may need retries', async () => {
    const { gateway, http } = gatewayReturning(apiAnswer)
    const postJson = vi.spyOn(http, 'postJson')

    await gateway.ask('Qual a pressão?')

    expect(postJson).toHaveBeenCalledWith(
      '/api/v1/questions',
      { question: 'Qual a pressão?' },
      expect.objectContaining({ timeoutMs: QUESTION_TIMEOUT_MS }),
    )
  })

  it('rejects answers outside the contract', async () => {
    const { gateway } = gatewayReturning({ answer: 'oi' })

    await expect(gateway.ask('Qual a pressão?')).rejects.toBeInstanceOf(InvalidResponseError)
  })

  it('links a citation to its PDF, opening at the first cited page', () => {
    const { gateway } = gatewayReturning(apiAnswer)
    const citation = { manualId: 'abc 123', manualTitle: 'X', pages: [7, 8], pagesLabel: 'p. 7-8' }

    expect(gateway.sourceUrl(citation)).toBe(
      'http://api.local/api/v1/manuals/abc%20123/file#page=7',
    )
    expect(gateway.sourceUrl({ ...citation, pages: [] })).toBe(
      'http://api.local/api/v1/manuals/abc%20123/file',
    )
  })
})
