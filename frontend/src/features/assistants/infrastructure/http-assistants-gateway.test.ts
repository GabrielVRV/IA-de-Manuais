import { describe, expect, it, vi } from 'vitest'

import { InvalidResponseError } from '@/shared/http/errors'
import { HttpClient } from '@/shared/http/http-client'

import { HttpAssistantsGateway } from './http-assistants-gateway'

function client(body: unknown) {
  const fetchFn = vi
    .fn<typeof fetch>()
    .mockImplementation(() => Promise.resolve(Response.json(body)))
  return { http: new HttpClient('http://api', { fetchFn }), fetchFn }
}

const policy = {
  assistant_id: 'engenharia',
  name: 'Assistente de Engenharia',
  default_access: 'restricted',
  request_instructions: 'Abra um chamado no GLPI.',
  updated_at: '2026-11-05T12:00:00Z',
  updated_by: 'Ana Admin',
}

describe('HttpAssistantsGateway', () => {
  it('maps whether the user can use each assistant', async () => {
    const { http } = client([
      {
        id: 'engenharia',
        name: 'Assistente de Engenharia',
        topic: 'Manuais técnicos',
        allowed: false,
        request_instructions: 'Abra um chamado no GLPI.',
      },
    ])

    expect(await new HttpAssistantsGateway(http).mine()).toEqual([
      {
        id: 'engenharia',
        name: 'Assistente de Engenharia',
        topic: 'Manuais técnicos',
        allowed: false,
        requestInstructions: 'Abra um chamado no GLPI.',
      },
    ])
  })

  it('saves a policy and maps the answer', async () => {
    const { http, fetchFn } = client(policy)

    const saved = await new HttpAssistantsGateway(http).updatePolicy('engenharia', {
      defaultAccess: 'restricted',
      requestInstructions: 'Abra um chamado no GLPI.',
    })

    expect(saved).toEqual({
      assistantId: 'engenharia',
      name: 'Assistente de Engenharia',
      defaultAccess: 'restricted',
      requestInstructions: 'Abra um chamado no GLPI.',
      updatedAt: new Date('2026-11-05T12:00:00Z'),
      updatedBy: 'Ana Admin',
    })
    expect(fetchFn).toHaveBeenCalledWith(
      'http://api/api/v1/assistants/engenharia/access',
      expect.objectContaining({ method: 'PUT' }),
    )
    const body = fetchFn.mock.calls[0]?.[1]?.body
    expect(typeof body === 'string' && JSON.parse(body)).toEqual({
      default_access: 'restricted',
      request_instructions: 'Abra um chamado no GLPI.',
    })
  })

  it('rejects an unknown assistant', async () => {
    const { http } = client([{ ...policy, assistant_id: 'ti' }])

    await expect(new HttpAssistantsGateway(http).policies()).rejects.toBeInstanceOf(
      InvalidResponseError,
    )
  })
})
