import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router'
import { Avatar } from '../../components/Crew'
import { ErrorState, LoadingState } from '../../components/States'
import type { SymbolDetail, SymbolMatch, WatchRow } from '../../lib/api'
import { bigMoney, pct, price, signedPct } from '../../lib/money'
import { useCrew } from '../../lib/crew'
import { useReadyWorkspace } from '../../lib/workspace'

const STARTERS = {
  in: [
    ['RELIANCE', 'Reliance Industries'],
    ['TCS', 'Tata Consultancy Services'],
    ['HDFCBANK', 'HDFC Bank'],
    ['^NSEI', 'Nifty 50 index'],
  ],
  us: [
    ['AAPL', 'Apple'],
    ['MSFT', 'Microsoft'],
    ['^GSPC', 'S&P 500 index'],
  ],
} as const

function direction(change: string | null): string {
  if (change == null) return ''
  const n = Number(change)
  return n > 0 ? 'up' : n < 0 ? 'down' : 'flat'
}

function RangeBar({ low, high, now, currency }: { low: string; high: string; now: string; currency: string }) {
  const lo = Number(low)
  const hi = Number(high)
  const at = hi > lo ? Math.min(Math.max((Number(now) - lo) / (hi - lo), 0), 1) : 0.5
  return (
    <div className="range">
      <div
        className="range-track"
        role="img"
        aria-label={`52-week range ${price(low, currency)} to ${price(high, currency)}, now ${price(now, currency)}`}
      >
        <span className="range-mark" style={{ left: `${at * 100}%` }} />
      </div>
      <div className="range-ends">
        <span>{price(low, currency)} low</span>
        <span>{price(high, currency)} high</span>
      </div>
    </div>
  )
}

function Detail({ detail }: { detail: SymbolDetail }) {
  const q = detail.quote
  const name = detail.profile?.name ?? q.name ?? q.symbol
  const ask = (crew: string, action: string, arg: string) =>
    `/app/chat/${crew}?${new URLSearchParams({ ask: action, arg })}`
  return (
    <div className="symbol-detail">
      <section className="quote-head" aria-label={`${name} price`}>
        <p className="quote-name">
          {name} <span className="muted">{q.symbol}{q.exchange ? `, ${q.exchange}` : ''}</span>
        </p>
        <p className="answer-big">
          {price(q.price, q.currency)}
          <span className="answer-unit">
            {' '}
            {direction(q.change_pct)}
            {q.change_pct != null && Number(q.change_pct) !== 0
              ? ` ${Math.abs(Number(q.change_pct)).toFixed(2)}%`
              : ''}{' '}
            today
          </span>
        </p>
        <div className="card-actions">
          <Link className="btn btn-soft" to={ask('bruno', 'check', q.symbol)}>
            Ask Bruno what this means
          </Link>
          <Link className="btn btn-soft" to={ask('scout', 'news', name)}>
            Ask Scout for the news
          </Link>
        </div>
      </section>
      {q.year_low && q.year_high && (
        <section aria-labelledby="range-title">
          <h2 id="range-title" className="section-title">
            Where it sits in its 52-week range
          </h2>
          <RangeBar low={q.year_low} high={q.year_high} now={q.price} currency={q.currency} />
        </section>
      )}

      <section aria-labelledby="year-title">
        <h2 id="year-title" className="section-title">
          The past year
        </h2>
        {detail.stats ? (
          <dl className="facts">
            <div>
              <dt>Return</dt>
              <dd>{signedPct(detail.stats.return_pct, 1)}</dd>
            </div>
            <div>
              <dt>Volatility</dt>
              <dd>{pct(detail.stats.annualised_volatility_pct)}</dd>
            </div>
            <div>
              <dt>Worst fall from a peak</dt>
              <dd>{signedPct(detail.stats.max_drawdown_pct, 1)}</dd>
            </div>
          </dl>
        ) : (
          <p className="muted">{detail.errors.stats ?? 'No price history available.'}</p>
        )}
        <p className="fine-print">
          Volatility is how much the price swings in a typical year. Money you may need within a
          few years is usually kept out of anything that can fall this far.
        </p>
      </section>

      {detail.profile && (detail.profile.sector || detail.profile.summary) && (
        <section aria-labelledby="company-title">
          <h2 id="company-title" className="section-title">
            The company
          </h2>
          <dl className="facts facts-small">
            {detail.profile.sector && (
              <div>
                <dt>Sector</dt>
                <dd>{detail.profile.sector}</dd>
              </div>
            )}
            {detail.profile.trailing_pe && (
              <div>
                <dt>Price to earnings</dt>
                <dd>{Number(detail.profile.trailing_pe).toFixed(1)}</dd>
              </div>
            )}
            {detail.profile.dividend_yield_pct && (
              <div>
                <dt>Dividend yield</dt>
                <dd>{pct(detail.profile.dividend_yield_pct)}</dd>
              </div>
            )}
            {q.market_cap && (
              <div>
                <dt>Market value</dt>
                <dd>{bigMoney(q.market_cap, q.currency)}</dd>
              </div>
            )}
          </dl>
          {detail.profile.summary && <p className="company-summary">{detail.profile.summary}</p>}
        </section>
      )}

      <section aria-labelledby="news-title">
        <h2 id="news-title" className="section-title">
          In the news
        </h2>
        {detail.news && detail.news.length > 0 ? (
          <ul className="news-list">
            {detail.news.map((n) => (
              <li key={n.link}>
                <a href={n.link} target="_blank" rel="noopener noreferrer">
                  {n.title}
                </a>
                <span className="muted">
                  {n.source}
                  {n.published &&
                    `, ${new Date(n.published).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })}`}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">{detail.errors.news ?? 'No recent headlines found.'}</p>
        )}
      </section>

      {detail.filings && detail.filings.length > 0 && (
        <section aria-labelledby="filings-title">
          <h2 id="filings-title" className="section-title">
            Recent SEC filings
          </h2>
          <ul className="news-list">
            {detail.filings.map((f) => (
              <li key={f.url}>
                <a href={f.url} target="_blank" rel="noopener noreferrer">
                  {f.form}
                  {f.description && f.description !== f.form ? `: ${f.description}` : ''}
                </a>
                <span className="muted">Filed {f.filed}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}

export function Markets() {
  const { data, api } = useReadyWorkspace()
  const [rows, setRows] = useState<WatchRow[] | null>(null)
  const [listError, setListError] = useState<string | null>(null)
  const [selected, setSelected] = useState<string | null>(data.watchlist[0] ?? null)
  const [detail, setDetail] = useState<SymbolDetail | null>(null)
  const [detailError, setDetailError] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [matches, setMatches] = useState<SymbolMatch[]>([])
  const [busy, setBusy] = useState(false)
  const [symbols, setSymbols] = useState<string[]>(data.watchlist)

  const loadRows = useCallback(() => {
    api
      .watchlist()
      .then((r) => {
        setRows(r)
        setListError(null)
      })
      .catch((e: Error) => setListError(e.message))
  }, [api])

  useEffect(loadRows, [loadRows])

  useEffect(() => {
    if (!selected) return
    let cancelled = false
    api
      .symbol(selected)
      .then((d) => {
        if (cancelled) return
        setDetail(d)
        setDetailError(null)
      })
      .catch((e: Error) => !cancelled && setDetailError(e.message))
    return () => {
      cancelled = true
    }
  }, [api, selected])

  useEffect(() => {
    const q = query.trim()
    if (q.length < 2) return
    let cancelled = false
    const t = setTimeout(() => {
      api
        .searchSymbols(q)
        .then((m) => !cancelled && setMatches(m.slice(0, 6)))
        .catch(() => !cancelled && setMatches([]))
    }, 300)
    return () => {
      cancelled = true
      clearTimeout(t)
    }
  }, [api, query])

  async function save(next: string[], select?: string) {
    setBusy(true)
    try {
      const saved = await api.setWatchlist(next)
      setSymbols(saved)
      if (select) {
        const normalized = saved.find((s) => s.startsWith(select.toUpperCase())) ?? saved.at(-1) ?? null
        setDetail(null)
        setSelected(normalized)
      } else if (selected && !saved.includes(selected)) {
        setDetail(null)
        setSelected(saved[0] ?? null)
      }
      loadRows()
    } catch (e) {
      setListError(e instanceof Error ? e.message : 'The watchlist wasn’t saved.')
    } finally {
      setBusy(false)
    }
  }

  function add(symbol: string) {
    setQuery('')
    setMatches([])
    if (symbols.length >= 20) {
      setListError('The watchlist holds up to 20 symbols. Remove one first.')
      return
    }
    void save([...symbols, symbol], symbol)
  }

  const { byId } = useCrew()

  return (
    <div className="page">
      <header className="page-intro page-intro-crew">
        <Avatar member={byId.bruno} size="lg" />
        <div>
          <h1 className="page-title">Bruno’s markets</h1>
          <p className="page-sub">
            Keep an eye on stocks and indices next to your own plan. Add one by name or ticker;
            Indian tickers default to NSE. Prices are delayed.
          </p>
        </div>
      </header>

      <div className="markets-grid">
        <section className="watch" aria-labelledby="watch-title">
          <h2 id="watch-title" className="section-title">
            Your watchlist
          </h2>
          <div className="symbol-search">
            <label htmlFor="symbol-search">Add a stock or index</label>
            <input
              id="symbol-search"
              type="search"
              autoComplete="off"
              placeholder={data.market === 'in' ? 'Infosys, TCS or ^NSEI' : 'Apple, MSFT or ^GSPC'}
              value={query}
              onChange={(e) => {
                setQuery(e.target.value)
                if (e.target.value.trim().length < 2) setMatches([])
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && query.trim()) {
                  e.preventDefault()
                  add(matches[0]?.symbol ?? query.trim())
                }
                if (e.key === 'Escape') setMatches([])
              }}
            />
            {matches.length > 0 && (
              <ul className="search-results" aria-label="Matching symbols">
                {matches.map((m) => (
                  <li key={m.symbol}>
                    <button type="button" disabled={busy} onClick={() => add(m.symbol)}>
                      <strong>{m.symbol}</strong> {m.name}
                      <span className="muted"> {m.exchange}</span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {listError && (
            <p className="field-error" role="alert">
              {listError}
            </p>
          )}

          {symbols.length === 0 ? (
            <div className="watch-empty">
              <p>Nothing here yet. Some to start with:</p>
              <div className="row-actions">
                {STARTERS[data.market].map(([symbol, label]) => (
                  <button key={symbol} type="button" className="btn btn-ghost" disabled={busy} onClick={() => add(symbol)}>
                    {label}
                  </button>
                ))}
              </div>
            </div>
          ) : rows === null ? (
            <LoadingState what="Fetching prices" />
          ) : (
            <ul className="watch-list">
              {rows.map((r) => (
                <li key={r.symbol} className={r.symbol === selected ? 'watch-row watch-row-active' : 'watch-row'}>
                  <button
                    type="button"
                    className="watch-pick"
                    aria-current={r.symbol === selected ? 'true' : undefined}
                    onClick={() => {
                      setDetail(null)
                      setSelected(r.symbol)
                    }}
                  >
                    <span className="watch-symbol">{r.symbol}</span>
                    {r.quote ? (
                      <span className="watch-price">
                        {price(r.quote.price, r.quote.currency)}{' '}
                        <span className="muted">{signedPct(r.quote.change_pct)}</span>
                      </span>
                    ) : (
                      <span className="field-error">No price</span>
                    )}
                  </button>
                  <button
                    type="button"
                    className="link-button watch-remove"
                    disabled={busy}
                    onClick={() => void save(symbols.filter((s) => s !== r.symbol))}
                  >
                    Remove<span className="visually-hidden"> {r.symbol}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>

        <div className="watch-detail" aria-live="polite">
          {selected && detailError && <ErrorState message={detailError} />}
          {selected && !detail && !detailError && <LoadingState what={`Loading ${selected}`} />}
          {detail && detail.symbol === selected && <Detail detail={detail} />}
        </div>
      </div>
    </div>
  )
}
