import type { Currency } from './api'

const LOCALE: Record<Currency, string> = { INR: 'en-IN', USD: 'en-US' }
const formatters = new Map<string, Intl.NumberFormat>()

function formatter(currency: Currency, decimals: number): Intl.NumberFormat {
  const key = `${currency}:${decimals}`
  let f = formatters.get(key)
  if (!f) {
    f = new Intl.NumberFormat(LOCALE[currency], {
      style: 'currency',
      currency,
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    })
    formatters.set(key, f)
  }
  return f
}

/** ₹12,34,567.50 (Indian grouping) or $1,234,567.50. `whole` drops paise/cents. */
export function money(value: string | number, currency: Currency, whole = false): string {
  return formatter(currency, whole ? 0 : 2).format(Number(value))
}

/** A market price in whatever currency the exchange quotes (INR, USD, or others). */
export function price(value: string | number, currency: string): string {
  try {
    return new Intl.NumberFormat(currency === 'INR' ? 'en-IN' : 'en-US', {
      style: 'currency',
      currency,
      maximumFractionDigits: 2,
    }).format(Number(value))
  } catch {
    return Number(value).toLocaleString('en-US', { maximumFractionDigits: 2 })
  }
}

/** Market cap the way each market says it: "₹16.10 lakh crore" or "$5.07T". */
export function bigMoney(value: string | number, currency: string): string {
  const n = Number(value)
  if (currency === 'INR') {
    if (n >= 1e12) return `₹${(n / 1e12).toFixed(2)} lakh crore`
    if (n >= 1e7) return `₹${(n / 1e7).toFixed(0)} crore`
  }
  try {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency,
      notation: 'compact',
      maximumFractionDigits: 2,
    }).format(n)
  } catch {
    return n.toLocaleString('en-US', { notation: 'compact' })
  }
}

/** "+0.46%" / "−0.21%" with a real minus sign. */
export function signedPct(value: string | number | null | undefined, digits = 2): string {
  if (value == null) return 'n/a'
  const n = Number(value)
  const body = `${Math.abs(n).toFixed(digits)}%`
  return n > 0 ? `+${body}` : n < 0 ? `−${body}` : body
}

export function pct(value: string | number | null | undefined): string {
  if (value == null) return 'n/a'
  return `${Number(value).toFixed(1).replace(/\.0$/, '')}%`
}

/** "Aug to Oct 2026" from ISO dates. */
export function periodLabel(startIso: string, endIso: string): string {
  const start = new Date(`${startIso}T00:00:00`)
  const end = new Date(`${endIso}T00:00:00`)
  const month = (d: Date) => d.toLocaleString('en-GB', { month: 'short' })
  if (start.getFullYear() === end.getFullYear() && start.getMonth() === end.getMonth()) {
    return `${month(end)} ${end.getFullYear()}`
  }
  if (start.getFullYear() === end.getFullYear()) {
    return `${month(start)} to ${month(end)} ${end.getFullYear()}`
  }
  return `${month(start)} ${start.getFullYear()} to ${month(end)} ${end.getFullYear()}`
}

/** "March 2028": the calendar month `months` from now. */
export function monthsFromNow(months: number): string {
  const d = new Date()
  d.setDate(1)
  d.setMonth(d.getMonth() + months)
  return d.toLocaleString('en-GB', { month: 'long', year: 'numeric' })
}
