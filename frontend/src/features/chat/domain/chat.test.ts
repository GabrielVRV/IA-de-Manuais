import { describe, expect, it } from 'vitest'

import { type ConversationSummary, groupByRecency, isValidTitle } from './chat'

const now = new Date(2026, 9, 10, 15, 0)

function at(date: Date, id = date.toISOString()): ConversationSummary {
  return { id, title: id, createdAt: date, updatedAt: date, exchangeCount: 1 }
}

describe('groupByRecency', () => {
  it('groups by the last use, keeping the given order and skipping empty groups', () => {
    const conversations = [
      at(new Date(2026, 9, 10, 9, 0), 'hoje'),
      at(new Date(2026, 9, 9, 23, 0), 'ontem'),
      at(new Date(2026, 9, 5), 'semana'),
      at(new Date(2026, 7, 1), 'antiga'),
    ]

    expect(
      groupByRecency(conversations, now).map((g) => [g.label, g.conversations.map((c) => c.id)]),
    ).toEqual([
      ['Hoje', ['hoje']],
      ['Ontem', ['ontem']],
      ['Últimos 7 dias', ['semana']],
      ['Mais antigas', ['antiga']],
    ])
  })

  it('returns nothing for an empty history', () => {
    expect(groupByRecency([], now)).toEqual([])
  })
})

describe('isValidTitle', () => {
  it.each([
    ['Pressão da P-200', true],
    ['   ', false],
    ['x'.repeat(81), false],
  ])('%s -> %s', (title, valid) => {
    expect(isValidTitle(title)).toBe(valid)
  })
})
