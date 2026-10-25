import { useState, type ReactNode } from 'react'
import { Link } from 'react-router'
import { AnimatedNumber } from '../../components/AnimatedNumber'
import { ApprovalSlip } from '../../components/ApprovalSlip'
import { Avatar, CrewName } from '../../components/Crew'
import { PayoffRace } from '../../components/PayoffRace'
import { hasComparison, type CrewId, type FiledBucket } from '../../lib/api'
import { useCrew } from '../../lib/crew'
import { raceVerdict } from '../../lib/insights'
import { money, monthsFromNow, pct, periodLabel } from '../../lib/money'
import { useReadyWorkspace } from '../../lib/workspace'

function Section({
  crew,
  question,
  children,
  wide = false,
}: {
  crew: CrewId
  question: string
  children: ReactNode
  wide?: boolean
}) {
  const { byId } = useCrew()
  const m = byId[crew]
  return (
    <section className={wide ? 'money-card money-card-wide' : 'money-card'} aria-labelledby={`q-${crew}`}>
      <header className="money-card-head">
        <Avatar member={m} size="md" />
        <div>
          <p className="money-card-who">{m && <CrewName id={crew}>{m.name}</CrewName>}</p>
          <h2 id={`q-${crew}`} className="money-card-q">
            {question}
          </h2>
        </div>
      </header>
      {children}
      {m && (
        <Link className="ask-link" to={`/app/chat/${crew}`}>
          Ask {m.name} about this
        </Link>
      )}
    </section>
  )
}

function Penny() {
  const { data, api, mutate } = useReadyWorkspace()
  const { spending, currency } = data
  const [showAll, setShowAll] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const rows = spending.buckets.filter((b) => b.bucket !== 'unclassified')
  const unfiled = spending.categories.filter((c) => c.bucket === 'unclassified')
  const guide: Record<string, string> = { needs: 'up to 50%', wants: 'up to 30%', savings: 'at least 20%' }
  const name: Record<string, string> = { needs: 'Needs', wants: 'Wants', savings: 'You keep' }
  const categories = showAll ? spending.categories : spending.categories.slice(0, 5)

  async function file(category: string, bucket: FiledBucket) {
    setError(null)
    try {
      await mutate(() => api.classify(category, bucket))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'That didn’t save. Try again.')
    }
  }

  return (
    <Section crew="penny" question="Can I save more?">
      <p className="answer-big">
        {money(spending.avg_monthly_savings, currency, true)}
        <span className="answer-unit"> left over each month</span>
      </p>
      <p className="answer-text">
        That’s {pct(spending.savings_rate_pct)} of your income, averaged over{' '}
        {periodLabel(spending.period_start, spending.period_end)}. The guide is to keep at least 20%.
      </p>
      <ul className="split-list">
        {rows.map((r) => (
          <li key={r.bucket}>
            <div className="split-row">
              <span className="split-name">{name[r.bucket]}</span>
              <span>
                {money(r.monthly_avg, currency, true)}{' '}
                <span className="muted">
                  ({pct(r.pct_of_income)}, guide {guide[r.bucket]})
                </span>
              </span>
            </div>
            <span className="bar crew-penny" aria-hidden="true">
              <span className="bar-fill" style={{ width: `${Math.min(Math.max(Number(r.pct_of_income ?? 0), 0), 100)}%` }} />
            </span>
          </li>
        ))}
      </ul>

      {unfiled.length > 0 && (
        <div className="nudge">
          {unfiled.map((c) => (
            <div key={c.category} className="nudge-item">
              <p>
                Is <strong>{c.category}</strong> ({money(c.monthly_avg, currency, true)} a month) a
                need, a want or savings?
              </p>
              <div className="card-actions" role="group" aria-label={`File ${c.category} as`}>
                <button className="btn btn-soft" onClick={() => void file(c.category, 'needs')}>
                  Need
                </button>
                <button className="btn btn-soft" onClick={() => void file(c.category, 'wants')}>
                  Want
                </button>
                <button className="btn btn-soft" onClick={() => void file(c.category, 'savings')}>
                  Savings
                </button>
              </div>
            </div>
          ))}
          {error && (
            <p className="field-error" role="alert">
              {error}
            </p>
          )}
        </div>
      )}

      <h3 className="mini-title">Where it goes</h3>
      <ul className="rows">
        {categories.map((c) => (
          <li key={c.category}>
            <span>
              {c.category}
              {c.bucket === 'unclassified' && <span className="muted"> (not sorted yet)</span>}
            </span>
            <strong>{money(c.monthly_avg, currency, true)}</strong>
          </li>
        ))}
      </ul>
      {spending.categories.length > 5 && (
        <button type="button" className="link-button" onClick={() => setShowAll((v) => !v)}>
          {showAll ? 'Show fewer' : `Show all ${spending.categories.length} categories`}
        </button>
      )}
    </Section>
  )
}

function Hazel() {
  const { data, contribution, setContribution, decide } = useReadyWorkspace()
  const { emergency_fund: ef, currency, spending } = data
  const p = ef.plan
  const target = Number(p.target_amount)
  const have = Number(p.current_balance)
  const surplus = Math.max(Number(spending.avg_monthly_savings), 0)
  const options = [0.25, 0.5, 1].map((s) => Math.round(surplus * s))
  const current = contribution ?? Number(p.monthly_contribution)

  return (
    <Section crew="hazel" question="Am I covered if something goes wrong?">
      <p className="answer-big">
        {p.coverage_months ?? '0'} of {p.target_months}
        <span className="answer-unit"> months of essentials covered</span>
      </p>
      <span className="bar bar-thick crew-hazel" aria-hidden="true">
        <span className="bar-fill" style={{ width: `${target ? Math.min(have / target, 1) * 100 : 100}%` }} />
      </span>
      <p className="answer-text">
        {money(have, currency, true)} saved of a {money(target, currency, true)} goal.
      </p>
      {!p.is_funded && (
        <>
          <h3 className="mini-title">How much could you put away each month?</h3>
          <div className="chips" role="group" aria-label="Monthly amount">
            {options.map((amount, i) => (
              <button
                key={i}
                type="button"
                className="chip"
                aria-pressed={Math.round(current) === amount}
                onClick={() => setContribution(amount)}
              >
                {money(amount, currency, true)}
              </button>
            ))}
          </div>
          {p.months_to_target != null && (
            <p className="answer-text">
              You’d be fully covered in{' '}
              <strong>
                <AnimatedNumber value={p.months_to_target} format={(n) => `${Math.round(n)} months`} />
              </strong>
              , around {monthsFromNow(p.months_to_target)}.
            </p>
          )}
          <ApprovalSlip
            key={p.monthly_contribution}
            subject={`Safety net: set aside ${money(p.monthly_contribution, currency)} a month to reach ${money(p.target_amount, currency)} in ${p.months_to_target} months`}
            onDecide={(d) =>
              decide(
                `Safety net: set aside ${money(p.monthly_contribution, currency)} a month to reach ${money(p.target_amount, currency)} in ${p.months_to_target} months`,
                d,
              )
            }
          />
        </>
      )}
    </Section>
  )
}

const STEPS = { in: [0, 2000, 5000, 10000], us: [0, 100, 300, 500] } as const

function Snowy() {
  const { data, extra, setExtra, decide } = useReadyWorkspace()
  const { debt, currency, market, profile } = data
  const [showDebts, setShowDebts] = useState(false)

  if (!hasComparison(debt)) {
    return (
      <Section crew="snowy" question="When will I be debt-free?" wide>
        <p className="answer-big">{'message' in debt ? 'You have no debts' : 'Let’s fix the plan'}</p>
        <p className="answer-text">
          {'error' in debt ? debt.error : 'Nothing to pay off. If that’s wrong, add your debts in Settings.'}
        </p>
      </Section>
    )
  }
  const best = debt.comparison[debt.comparison.cheapest]
  const subject = `Debt plan: ${debt.comparison.cheapest}, ${money(debt.monthly_budget, currency)} a month`

  return (
    <Section crew="snowy" question="When will I be debt-free?" wide>
      <p className="answer-big">
        <AnimatedNumber value={best.months} format={(n) => monthsFromNow(Math.round(n))} />
        <span className="answer-unit"> ({best.months} months)</span>
      </p>
      <p className="answer-text">
        Paying {money(debt.monthly_budget, currency, true)} a month (
        {extra ? `${money(debt.sum_of_minimums, currency, true)} minimums plus ${money(extra, currency, true)} extra` : 'just your minimum payments'}
        ), with {money(best.total_interest, currency, true)} of interest along the way.
      </p>
      <h3 className="mini-title">What if you paid a bit more each month?</h3>
      <div className="chips" role="group" aria-label="Extra each month">
        {STEPS[market].map((amount) => (
          <button
            key={amount}
            type="button"
            className="chip"
            aria-pressed={extra === amount}
            onClick={() => setExtra(amount)}
          >
            {amount === 0 ? 'Just minimums' : `+${money(amount, currency, true)}`}
          </button>
        ))}
      </div>
      <PayoffRace debt={debt} currency={currency} />
      <p className="answer-text">{raceVerdict(debt, currency)}</p>
      <ApprovalSlip key={subject} subject={subject} onDecide={(d) => decide(subject, d)} />
      <button type="button" className="link-button" onClick={() => setShowDebts((v) => !v)} aria-expanded={showDebts}>
        {showDebts ? 'Hide your debts' : `See your ${profile.debts.length} debts`}
      </button>
      {showDebts && (
        <ul className="rows">
          {profile.debts.map((d) => (
            <li key={d.name}>
              <span>
                {d.name} <span className="muted">at {Number(d.annual_rate_pct)}% a year</span>
              </span>
              <strong>{money(d.balance, currency, true)}</strong>
            </li>
          ))}
        </ul>
      )}
    </Section>
  )
}

export function Money() {
  const { data } = useReadyWorkspace()
  return (
    <div className="page">
      <header className="page-intro">
        <h1 className="page-title">Your money</h1>
        <p className="page-sub">
          Three questions most people ask, answered from your own numbers. Each one belongs to a
          member of the crew, so you know who to ask.
        </p>
        {data.sources.transactions === 'sample' && (
          <p className="page-note">
            These are sample numbers. <Link to="/app/settings#data">Upload your own statement</Link>{' '}
            to make them yours.
          </p>
        )}
      </header>
      <div className="money-grid">
        <Penny />
        <Hazel />
        <Snowy />
      </div>
    </div>
  )
}
