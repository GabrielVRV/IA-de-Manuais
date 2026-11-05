/** Aceita "0,40" (vírgula, como se digita no Brasil) e "0.40". Vazio ou inválido = null. */
export function parsePrice(text: string): number | null {
  const normalized = text.trim().replace(',', '.')
  if (normalized === '' || !/^\d+(\.\d+)?$/.test(normalized)) return null
  return Number(normalized)
}

export function priceText(value: number | null): string {
  return value === null ? '' : String(value).replace('.', ',')
}
