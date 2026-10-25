import { useState } from 'react'
import type { Currency, DebtComparison, PayoffPlan } from '../lib/api'
import { money } from '../lib/money'

const STRATEGY: Record<PayoffPlan['strategy'], { name: string; rule: string }> = {
  avalanche: { name: 'Avalanche', rule: 'highest interest rate first' },
  snowball: { name: 'Snowball', rule: 'smallest balance first' },
}

type Marker = PayoffPlan['payoff_order'][number] & { left: number; below: boolean }

function Lane({ plan, max, currency }: { plan: PayoffPlan; max: number; currency: Currency }) {
  const [active, setActive] = useState<string | null>(null)
  const x = (m: number) => (m / max) * 100
  // Alternate labels above/below when two debts clear close together.
  const markers = plan.payoff_order.reduce<Marker[]>((acc, p) => {
    const left = x(p.month_paid_off)
    const prev = acc.at(-1)
    return [...acc, { ...p, left, below: prev && left - prev.left < 20 ? !prev.below : false }]
  }, [])
  const tip = markers.find((m) => m.name === active)

  return (
    <div className="lane">
      <div className="lane-head">
        <p>
          <strong>{STRATEGY[plan.strategy].name}</strong>{' '}
          <span className="muted">pays the {STRATEGY[plan.strategy].rule}</span>
        </p>
        <p className="lane-total">
          {plan.months} months, {money(plan.total_interest, currency, true)} interest
        </p>
      </div>
      <div className="lane-track" onMouseLeave={() => setActive(null)}>
        <span className="lane-line" style={{ width: `${x(plan.months)}%` }} />
        {markers.map((m) => (
          <button
            key={m.name}
            type="button"
            className="lane-marker"
            style={{ left: `${m.left}%` }}
            aria-label={`${m.name}: paid off in month ${m.month_paid_off}, ${money(m.interest_paid, currency)} interest`}
            onMouseEnter={() => setActive(m.name)}
            onFocus={() => setActive(m.name)}
            onBlur={() => setActive(null)}
            onClick={() => setActive(active === m.name ? null : m.name)}
          >
            <span className="lane-dot" aria-hidden="true" />
            <span
              aria-hidden="true"
              className={[
                'lane-label',
                m.below && 'lane-label-below',
                m.left > 78 && 'lane-label-end',
                m.left < 22 && 'lane-label-start',
              ]
                .filter(Boolean)
                .join(' ')}
            >
              {m.name}
            </span>
          </button>
        ))}
      </div>
      <p className="lane-tip" aria-live="polite">
        {tip
          ? `${tip.name} is paid off in month ${tip.month_paid_off}, after ${money(tip.interest_paid, currency)} of interest.`
          : ' '}
      </p>
    </div>
  )
}

/** Two payoff lanes on one month axis. Each dot is the month a debt is gone. */
export function PayoffRace({ debt, currency }: { debt: DebtComparison; currency: Currency }) {
  const { avalanche, snowball } = debt.comparison
  const max = Math.max(avalanche.months, snowball.months)
  const step = max > 36 ? 12 : 6
  const ticks = Array.from({ length: Math.floor(max / step) + 1 }, (_, i) => i * step)

  return (
    <figure className="race">
      <figcaption className="visually-hidden">
        Months until each debt is paid off, avalanche compared with snowball
      </figcaption>
      <Lane plan={avalanche} max={max} currency={currency} />
      <Lane plan={snowball} max={max} currency={currency} />
      <div className="race-axis" aria-hidden="true">
        {ticks.map((m) => (
          <span key={m} style={{ left: `${(m / max) * 100}%` }}>
            {m === 0 ? 'Now' : `${m} mo`}
          </span>
        ))}
      </div>
    </figure>
  )
}
