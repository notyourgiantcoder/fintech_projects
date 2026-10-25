import { Link, useNavigate } from 'react-router'
import { hasComparison, type CrewId } from '../lib/api'
import { useCrew } from '../lib/crew'
import { money, monthsFromNow } from '../lib/money'
import { useReadyWorkspace } from '../lib/workspace'
import { Avatar } from './Crew'

/** Four numbers people care about, each one tap away from the crew member who owns it. */
export function MoneyPanel() {
  const { data } = useReadyWorkspace()
  const { byId } = useCrew()
  const navigate = useNavigate()
  const { spending, emergency_fund: ef, debt, currency, approvals } = data
  const plan = ef.plan
  const best = hasComparison(debt) ? debt.comparison[debt.comparison.cheapest] : null
  const decided = (prefix: string) => approvals.some((a) => a.subject.startsWith(prefix))
  const waiting =
    spending.unclassified_categories.length +
    (best && !decided('Debt plan') ? 1 : 0) +
    (!plan.is_funded && !decided('Safety net') ? 1 : 0)

  const rows: { crew: CrewId; ask: string; label: string; value: string; progress?: number }[] = [
    {
      crew: 'penny',
      ask: 'spending',
      label: 'Left over each month',
      value: money(spending.avg_monthly_savings, currency, true),
    },
    {
      crew: 'hazel',
      ask: 'safety_net',
      label: 'Safety net',
      value: `${plan.coverage_months ?? 0} of ${plan.target_months} months`,
      progress: Number(plan.target_amount) ? Number(plan.current_balance) / Number(plan.target_amount) : 1,
    },
    {
      crew: 'snowy',
      ask: 'debt_free',
      label: 'Debt-free',
      value: best ? monthsFromNow(best.months) : 'No debts',
    },
    {
      crew: 'finbo',
      ask: 'attention',
      label: 'Waiting on you',
      value: waiting === 0 ? 'Nothing' : `${waiting} thing${waiting === 1 ? '' : 's'}`,
    },
  ]

  return (
    <aside className="money-panel" aria-labelledby="money-panel-title">
      <h2 id="money-panel-title" className="panel-title">
        My money
      </h2>
      <ul className="panel-list">
        {rows.map((r) => (
          <li key={r.crew}>
            <button
              type="button"
              className="panel-row"
              onClick={() => navigate(`/app/chat/${r.crew}?ask=${r.ask}`)}
            >
              <Avatar member={byId[r.crew]} size="sm" />
              <span className="panel-text">
                <span className="panel-label">{r.label}</span>
                <span className="panel-value">{r.value}</span>
                {r.progress !== undefined && (
                  <span className={`bar crew-${r.crew}`} aria-hidden="true">
                    <span className="bar-fill" style={{ width: `${Math.min(r.progress, 1) * 100}%` }} />
                  </span>
                )}
              </span>
              <span className="visually-hidden">Ask {byId[r.crew]?.name}</span>
            </button>
          </li>
        ))}
      </ul>
      <Link to="/app/money" className="panel-more">
        See the full picture
      </Link>
      {data.sources.transactions === 'sample' && (
        <p className="panel-note">
          You’re looking at sample data. <Link to="/app/settings#data">Use your own statement</Link>
        </p>
      )}
    </aside>
  )
}
