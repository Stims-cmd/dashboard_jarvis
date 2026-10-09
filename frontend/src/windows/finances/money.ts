// Amounts travel as integer cents and rates as basis points (150 = 1,50 %):
// conversions are done on strings, never with floating-point arithmetic.

const euros = new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR' })

export function formatCents(cents: number | null | undefined): string {
  return cents === null || cents === undefined ? '—' : euros.format(cents / 100)
}

export function formatRate(bp: number | null | undefined): string {
  return bp === null || bp === undefined ? '—' : `${(bp / 100).toFixed(2).replace('.', ',')} %`
}

function parseDecimal(input: string, decimals: number): number | null {
  const cleaned = input.replace(/[\s €%]/g, '').replace(',', '.')
  const match = /^(-?)(\d+)(?:\.(\d+))?$/.exec(cleaned)
  if (!match || (match[3] ?? '').length > decimals) return null
  const [, sign, whole, fraction = ''] = match
  const value = Number(whole) * 10 ** decimals + Number(fraction.padEnd(decimals, '0'))
  return sign ? -value : value
}

/** "1 234,56" -> 123456, or null if invalid. */
export const parseEuros = (input: string) => parseDecimal(input, 2)

/** "1,70" -> 170 basis points, or null if invalid. */
export const parseRate = (input: string) => parseDecimal(input, 2)
