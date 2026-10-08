// Sem caracteres ambíguos (l/1, O/0): a senha provisória é ditada ou digitada por outra pessoa.
export const PASSWORD_ALPHABET = 'abcdefghjkmnpqrstuvwxyz23456789'
const GROUPS = 3
const GROUP_SIZE = 4

/**
 * Senha provisória aleatória no formato "abcd-efgh-jkmn" (~59 bits de entropia).
 * Usa crypto.getRandomValues, que, ao contrário de crypto.randomUUID, funciona em HTTP.
 */
export function randomPassword(): string {
  const values = crypto.getRandomValues(new Uint32Array(GROUPS * GROUP_SIZE))
  const chars = Array.from(
    values,
    (value) => PASSWORD_ALPHABET[value % PASSWORD_ALPHABET.length] ?? 'a',
  )
  return Array.from({ length: GROUPS }, (_, group) =>
    chars.slice(group * GROUP_SIZE, (group + 1) * GROUP_SIZE).join(''),
  ).join('-')
}
