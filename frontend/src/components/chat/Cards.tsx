import type { CardAction, ChatCard } from '../../lib/api'

/* Values arrive pre-formatted by the server (the same strings Telegram shows), so the web
   and the bot can never disagree on a figure. */

interface Props {
  card: ChatCard
  busy: boolean
  onAction: (index: number) => void
}

function Tile({ label, value }: { label: string; value: string }) {
  return (
    <div className="tile">
      <span className="tile-label">{label}</span>
      <span className="tile-value">{value}</span>
    </div>
  )
}

function Bar({ value, crew }: { value: number; crew: string }) {
  return (
    <span className={`bar crew-${crew}`} aria-hidden="true">
      <span className="bar-fill" style={{ width: `${Math.max(Math.min(value, 1), 0) * 100}%` }} />
    </span>
  )
}

function Body({ card }: { card: ChatCard }) {
  const d = card.data
  switch (card.kind) {
    case 'summary':
      return (
        <div className="tiles">
          <Tile label="Left over each month" value={d.left_over} />
          <Tile label="You keep" value={`${d.savings_rate} of income`} />
          <Tile label="Safety net" value={d.safety} />
          <Tile label="Debt-free" value={d.debt_free} />
        </div>
      )
    case 'spending':
      return (
        <>
          <p className="card-lead">
            {d.spending} spent of {d.income} a month
          </p>
          <ul className="split-list">
            {d.rows.map((r: { label: string; amount: string; pct: number; pct_text: string; guide: string }) => (
              <li key={r.label}>
                <div className="split-row">
                  <span className="split-name">{r.label}</span>
                  <span>
                    {r.amount} <span className="muted">({r.pct_text}, guide {r.guide})</span>
                  </span>
                </div>
                <Bar value={r.pct / 100} crew="penny" />
              </li>
            ))}
          </ul>
          <p className="card-foot">
            Biggest: {d.top.slice(0, 3).map((t: { category: string; amount: string }) => `${t.category} ${t.amount}`).join(', ')}
          </p>
        </>
      )
    case 'safety':
      return (
        <>
          <p className="card-big">
            {d.have} <span className="muted">of {d.target}</span>
          </p>
          <Bar value={d.progress} crew="hazel" />
          <p className="card-foot">
            {d.funded
              ? `Full: ${d.target_months} months of essentials covered.`
              : `${d.gap} to go. About ${d.months_to_target} months at ${d.monthly} a month.`}
          </p>
        </>
      )
    case 'debt':
      return (
        <>
          <p className="card-big">
            {d.debt_free} <span className="muted">({d.months} months)</span>
          </p>
          <p className="card-lead">
            Paying {d.monthly} a month, {d.interest} interest in total, {d.method} method.
          </p>
          <ol className="timeline">
            {d.order.map((o: { name: string; when: string }) => (
              <li key={o.name}>
                <span>{o.name}</span>
                <span className="muted">paid off {o.when}</span>
              </li>
            ))}
          </ol>
        </>
      )
    case 'quote':
      return (
        <>
          <p className="card-big">
            {d.price}{' '}
            <span className="muted">
              {d.change > 0 ? 'up' : d.change < 0 ? 'down' : 'flat'} {d.change_text.replace(/^[+−]/, '')} today
            </span>
          </p>
          {d.return_1y && (
            <div className="tiles">
              <Tile label="Past year" value={d.return_1y} />
              <Tile label="Typical swing" value={d.volatility} />
              <Tile label="Worst fall" value={d.worst_fall} />
            </div>
          )}
          {d.year_low && (
            <p className="card-foot">
              52-week range {d.year_low} to {d.year_high}. Delayed prices from Yahoo Finance.
            </p>
          )}
        </>
      )
    case 'watchlist':
      return (
        <ul className="rows">
          {d.rows.map((r: { symbol: string; price: string; change_text: string }) => (
            <li key={r.symbol}>
              <strong>{r.symbol}</strong>
              <span>
                {r.price} <span className="muted">{r.change_text}</span>
              </span>
            </li>
          ))}
        </ul>
      )
    case 'news':
      return (
        <ul className="news">
          {d.items.map((n: { title: string; link: string; source: string | null; date: string | null }) => (
            <li key={n.link}>
              <a href={n.link} target="_blank" rel="noopener noreferrer">
                {n.title}
              </a>
              <span className="muted">{[n.source, n.date].filter(Boolean).join(', ')}</span>
            </li>
          ))}
        </ul>
      )
    case 'todo':
      return (
        <ul className="todo">
          {d.items.map((i: { text: string }) => (
            <li key={i.text}>{i.text}</li>
          ))}
        </ul>
      )
    case 'options':
      return (
        <ul className="rows">
          {d.rows.map((r: { label: string; value: string }) => (
            <li key={r.label}>
              <span>{r.label}</span>
              <strong>{r.value}</strong>
            </li>
          ))}
        </ul>
      )
    default:
      return null
  }
}

function buttonClass(a: CardAction): string {
  if (a.kind === 'approve') return 'btn btn-accent'
  if (a.kind === 'quick') return 'chip'
  return 'btn btn-soft'
}

export function Card({ card, busy, onAction }: Props) {
  return (
    <section className={`card card-${card.kind}`} aria-label={card.title}>
      <h3 className="card-title">{card.title}</h3>
      <Body card={card} />
      {card.outcome && (
        <p className="outcome" role="status">
          {card.outcome}
        </p>
      )}
      {card.actions.length > 0 && (
        <div className={card.kind === 'file' ? 'card-actions card-actions-file' : 'card-actions'}>
          {card.actions.map((a, i) => (
            <button key={`${a.label}-${i}`} type="button" className={buttonClass(a)} disabled={busy} onClick={() => onAction(i)}>
              {a.label}
            </button>
          ))}
        </div>
      )}
    </section>
  )
}
