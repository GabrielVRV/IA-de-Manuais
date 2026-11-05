/** Custos pequenos (centavos de dólar) precisam de mais casas para não virarem "US$ 0,00". */
export function formatUsd(value: number): string {
  return new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: value > 0 && value < 1 ? 4 : 2,
  }).format(value)
}
