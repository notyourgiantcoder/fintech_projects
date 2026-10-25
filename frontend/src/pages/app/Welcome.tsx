import { useState } from 'react'
import { Navigate, useNavigate } from 'react-router'
import { Avatar } from '../../components/Crew'
import type { Market } from '../../lib/api'
import { useCrew } from '../../lib/crew'
import { SAMPLE_PERSONA } from '../../lib/insights'
import { useWorkspace } from '../../lib/workspace'

const OPTIONS: { market: Market; name: string; detail: string }[] = [
  { market: 'in', name: 'India', detail: 'Rupees, lakh and crore, NSE and BSE.' },
  { market: 'us', name: 'United States', detail: 'Dollars, NYSE and Nasdaq.' },
]

export function Welcome() {
  const ws = useWorkspace()
  const { list, byId } = useCrew()
  const navigate = useNavigate()
  const [market, setMarket] = useState<Market>('in')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (ws.status === 'ready' && ws.data && !busy) return <Navigate to="/app" replace />

  async function start() {
    setBusy(true)
    setError(null)
    try {
      await ws.setup(market)
      navigate('/app/chat/finbo?ask=glance')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Your space wasn’t created. Try again.')
      setBusy(false)
    }
  }

  return (
    <div className="welcome">
      <div className="welcome-hello">
        <Avatar member={byId.finbo} size="xl" />
        <div>
          <h1 className="page-title">Hi, I’m Finbo.</h1>
          <p className="page-sub">
            My crew and I help you understand your money and decide what to do next. Here’s who
            you’ll meet:
          </p>
        </div>
      </div>
      <ul className="welcome-crew">
        {list
          .filter((m) => m.id !== 'finbo')
          .map((m) => (
            <li key={m.id}>
              <Avatar member={m} size="md" />
              <span>
                <strong>{m.name}</strong> {m.role.toLowerCase()}
              </span>
            </li>
          ))}
      </ul>

      <fieldset className="choice-cards">
        <legend>First, where do you bank?</legend>
        {OPTIONS.map((o) => (
          <label key={o.market} className="choice-card">
            <input
              type="radio"
              name="market"
              value={o.market}
              checked={market === o.market}
              onChange={() => setMarket(o.market)}
            />
            <span className="choice-name">{o.name}</span>
            <span className="choice-detail">
              {o.detail} We’ll start you on sample numbers for {SAMPLE_PERSONA[o.market]}; swap in
              your own statement whenever you like.
            </span>
          </label>
        ))}
      </fieldset>
      <button className="btn btn-primary btn-large" onClick={start} disabled={busy}>
        {busy ? 'Setting things up' : 'Meet the crew'}
      </button>
      {error && (
        <p className="field-error" role="alert">
          {error}
        </p>
      )}
    </div>
  )
}
