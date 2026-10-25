// Plain-language sentences derived from engine results. They restate numbers the engine
// produced; nothing here calculates money.
import type { Currency, DebtComparison, Workspace } from './api'
import { money } from './money'

export function raceVerdict(debt: DebtComparison, currency: Currency): string {
  const c = debt.comparison
  const saved = Number(c.interest_saved_with_avalanche)
  if (saved === 0 && c.earlier_first_win_with_snowball === 0) {
    return 'At this budget both methods cost the same. Add extra money each month to see them differ.'
  }
  const first =
    c.earlier_first_win_with_snowball > 0
      ? ` Snowball clears its first debt ${c.earlier_first_win_with_snowball} month${c.earlier_first_win_with_snowball === 1 ? '' : 's'} sooner, which helps if early wins keep you going.`
      : ''
  return `Avalanche saves ${money(Math.abs(saved), currency)} in interest.${first}`
}

/** Sample-data sources the person hasn't replaced yet. */
export function sampleParts(ws: Workspace): string[] {
  const parts = []
  if (ws.sources.transactions === 'sample') parts.push('transactions')
  if (ws.sources.profile === 'sample') parts.push('income and debts')
  return parts
}

export const SAMPLE_PERSONA: Record<Workspace['market'], string> = {
  in: 'a salaried professional in Pune',
  us: 'a renter in the United States',
}
