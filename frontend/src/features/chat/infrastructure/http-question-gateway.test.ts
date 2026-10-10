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

const mappedAnswer = {
  text: 'A pressão máxima é **10 bar**.',
  found: true,
  citations: [
    { manualId: 'abc-123', manualTitle: 'Compressor CX-500', pages: [3, 4], pagesLabel: 'p. 3-4' },
  ],
}

const apiReply = { ...apiAnswer, conversation: { id: 'c1', title: 'Qual a pressão?' } }

function gatewayReturning(body: unknown) {
  const fetchFn = vi
    .fn<typeof fetch>()
    .mockResolvedValue(body === null ? new Response(null, { status: 204 }) : Response.json(body))
  const http = new HttpClient('http://api.local', { fetchFn })
  return { gateway: new HttpQuestionGateway(http), fetchFn, http }
}

describe('HttpQuestionGateway', () => {
  it('starts a conversation with the first question and maps the answer', async () => {
    const { gateway, fetchFn } = gatewayReturning(apiReply)

    const reply = await gateway.ask('Qual a pressão?', null)

    expect(reply).toEqual({
      answer: mappedAnswer,
      conversation: { id: 'c1', title: 'Qual a pressão?' },
    })
    expect(fetchFn).toHaveBeenCalledWith(
      'http://api.local/api/v1/questions',
      expect.objectContaining({ method: 'POST', body: '{"question":"Qual a pressão?"}' }),
    )
  })

  it('continues an existing conversation', async () => {
    const { gateway, fetchFn } = gatewayReturning(apiReply)

    await gateway.ask('E a mínima?', 'c1')

    expect(fetchFn).toHaveBeenCalledWith(
      'http://api.local/api/v1/questions',
      expect.objectContaining({ body: '{"question":"E a mínima?","conversation_id":"c1"}' }),
    )
  })

  it('uses a long timeout, since the AI provider may need retries', async () => {
    const { gateway, http } = gatewayReturning(apiReply)
    const postJson = vi.spyOn(http, 'postJson')

    await gateway.ask('Qual a pressão?', null)

    expect(postJson).toHaveBeenCalledWith(
      '/api/v1/questions',
      { question: 'Qual a pressão?' },
      expect.objectContaining({ timeoutMs: QUESTION_TIMEOUT_MS }),
    )
  })

  it('rejects answers outside the contract', async () => {
    const { gateway } = gatewayReturning({ answer: 'oi' })

    await expect(gateway.ask('Qual a pressão?', null)).rejects.toBeInstanceOf(InvalidResponseError)
  })

  it('lists the history with dates', async () => {
    const { gateway } = gatewayReturning([
      {
        id: 'c1',
        title: 'Pressão da P-200',
        created_at: '2026-10-07T10:00:00Z',
        updated_at: '2026-10-08T09:30:00Z',
        exchange_count: 3,
      },
    ])

    expect(await gateway.listConversations()).toEqual([
      {
        id: 'c1',
        title: 'Pressão da P-200',
        createdAt: new Date('2026-10-07T10:00:00Z'),
        updatedAt: new Date('2026-10-08T09:30:00Z'),
        exchangeCount: 3,
      },
    ])
  })

  it('opens a conversation with its exchanges', async () => {
    const { gateway, fetchFn } = gatewayReturning({
      id: 'c 1',
      title: 'Pressão',
      created_at: '2026-10-07T10:00:00Z',
      updated_at: '2026-10-07T10:05:00Z',
      exchanges: [
        { question: 'Qual a pressão?', answer: apiAnswer, asked_at: '2026-10-07T10:00:00Z' },
      ],
    })

    const conversation = await gateway.getConversation('c 1')

    expect(conversation.exchanges).toEqual([
      {
        question: 'Qual a pressão?',
        answer: mappedAnswer,
        askedAt: new Date('2026-10-07T10:00:00Z'),
      },
    ])
    expect(fetchFn).toHaveBeenCalledWith(
      'http://api.local/api/v1/conversations/c%201',
      expect.anything(),
    )
  })

  it('renames and deletes conversations', async () => {
    const renaming = gatewayReturning({ id: 'c1', title: 'Novo título' })
    expect(await renaming.gateway.renameConversation('c1', 'Novo título')).toEqual({
      id: 'c1',
      title: 'Novo título',
    })
    expect(renaming.fetchFn).toHaveBeenCalledWith(
      'http://api.local/api/v1/conversations/c1',
      expect.objectContaining({ method: 'PATCH', body: '{"title":"Novo título"}' }),
    )

    const deleting = gatewayReturning(null)
    await deleting.gateway.deleteConversation('c1')
    expect(deleting.fetchFn).toHaveBeenCalledWith(
      'http://api.local/api/v1/conversations/c1',
      expect.objectContaining({ method: 'DELETE' }),
    )
  })

  it('links a citation to its PDF, opening at the first cited page', () => {
    const { gateway } = gatewayReturning(apiReply)
    const citation = { manualId: 'abc 123', manualTitle: 'X', pages: [7, 8], pagesLabel: 'p. 7-8' }

    expect(gateway.sourceUrl(citation)).toBe(
      'http://api.local/api/v1/manuals/abc%20123/file#page=7',
    )
    expect(gateway.sourceUrl({ ...citation, pages: [] })).toBe(
      'http://api.local/api/v1/manuals/abc%20123/file',
    )
  })
})
