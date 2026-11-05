import { z } from 'zod'

import { InvalidResponseError } from '@/shared/http/errors'
import type { HttpClient } from '@/shared/http/http-client'

import type {
  AccessPolicy,
  AccessPolicyChanges,
  AssistantId,
  AssistantsGateway,
  AvailableAssistant,
} from '../domain/assistants'

export const assistantIdSchema = z.enum(['engenharia'])

const availableSchema = z.object({
  id: assistantIdSchema,
  name: z.string(),
  topic: z.string(),
  allowed: z.boolean(),
  request_instructions: z.string(),
})

const policySchema = z.object({
  assistant_id: assistantIdSchema,
  name: z.string(),
  default_access: z.enum(['open', 'restricted']),
  request_instructions: z.string().nullable(),
  updated_at: z.iso.datetime({ offset: true }).nullable(),
  updated_by: z.string().nullable(),
})

function parse<T>(schema: z.ZodType<T>, body: unknown): T {
  const result = schema.safeParse(body)
  if (!result.success) throw new InvalidResponseError({ cause: result.error })
  return result.data
}

function toPolicy(body: unknown): AccessPolicy {
  const p = parse(policySchema, body)
  return {
    assistantId: p.assistant_id,
    name: p.name,
    defaultAccess: p.default_access,
    requestInstructions: p.request_instructions,
    updatedAt: p.updated_at ? new Date(p.updated_at) : null,
    updatedBy: p.updated_by,
  }
}

export class HttpAssistantsGateway implements AssistantsGateway {
  readonly #http: HttpClient

  constructor(http: HttpClient) {
    this.#http = http
  }

  async mine(): Promise<AvailableAssistant[]> {
    const body = parse(z.array(availableSchema), await this.#http.getJson('/api/v1/assistants'))
    return body.map((a) => ({
      id: a.id,
      name: a.name,
      topic: a.topic,
      allowed: a.allowed,
      requestInstructions: a.request_instructions,
    }))
  }

  async policies(): Promise<AccessPolicy[]> {
    const body = await this.#http.getJson('/api/v1/assistants/access')
    if (!Array.isArray(body)) throw new InvalidResponseError()
    return body.map(toPolicy)
  }

  async updatePolicy(
    assistantId: AssistantId,
    changes: AccessPolicyChanges,
  ): Promise<AccessPolicy> {
    return toPolicy(
      await this.#http.putJson(`/api/v1/assistants/${encodeURIComponent(assistantId)}/access`, {
        default_access: changes.defaultAccess,
        request_instructions: changes.requestInstructions,
      }),
    )
  }
}
