import { useEffect, useState } from 'react'
import Markdown from 'react-markdown'
import { Link } from 'react-router'
import { Card } from '../components/chat/Cards'
import { Avatar, CrewName } from '../components/Crew'
import { ErrorState, LoadingState } from '../components/States'
import { publicApi, type CrewId, type DemoReply, type Health, type Market } from '../lib/api'
import { useCrew } from '../lib/crew'
import { SAMPLE_PERSONA } from '../lib/insights'

const DEMO_QUESTIONS: { agent: CrewId; action: string; label: string }[] = [
  { agent: 'snowy', action: 'debt_free', label: 'When will I be debt-free?' },
  { agent: 'hazel', action: 'safety_net', label: 'How big should my safety net be?' },
  { agent: 'penny', action: 'spending', label: 'Where does my money go?' },
  { agent: 'snowy', action: 'compare', label: 'Avalanche or snowball?' },
]

function Demo() {
  const { byId } = useCrew()
  const [market, setMarket] = useState<Market>('in')
  const [pick, setPick] = useState(0)
  const [reply, setReply] = useState<DemoReply | null>(null)
  const [error, setError] = useState<string | null>(null)
  const q = DEMO_QUESTIONS[pick]

  useEffect(() => {
    let cancelled = false
    publicApi
      .demoQuick(q.agent, q.action, market)
      .then((r) => {
        if (cancelled) return
        setReply(r)
        setError(null)
      })
      .catch((e: Error) => !cancelled && setError(e.message))
    return () => {
      cancelled = true
    }
  }, [q.agent, q.action, market])

  const author = reply ? byId[reply.author] : undefined
  return (
    <section className="demo" id="demo" aria-labelledby="demo-title">
      <div className="demo-intro">
        <h2 id="demo-title" className="section-title">
          Ask a question, get a straight answer
        </h2>
        <p>
          This is the real Finbo, answering on sample numbers for {SAMPLE_PERSONA[market]}. Pick a
          question.
        </p>
        <div className="chips" role="group" aria-label="Country">
          {(['in', 'us'] as const).map((m) => (
            <button key={m} type="button" className="chip" aria-pressed={market === m} onClick={() => setMarket(m)}>
              {m === 'in' ? 'India' : 'United States'}
            </button>
          ))}
        </div>
        <div className="demo-questions" role="group" aria-label="Questions">
          {DEMO_QUESTIONS.map((d, i) => (
            <button key={d.label} type="button" className="chip chip-question" aria-pressed={pick === i} onClick={() => setPick(i)}>
              {d.label}
            </button>
          ))}
        </div>
      </div>
      <ol className="messages demo-chat" aria-live="polite">
        <li className="msg msg-user">
          <div className="bubble bubble-user">{q.label}</div>
        </li>
        {error && (
          <li>
            <ErrorState message="The demo didn’t load.">
              <p>{error}</p>
            </ErrorState>
          </li>
        )}
        {!error && !reply && (
          <li>
            <LoadingState what="Working it out" />
          </li>
        )}
        {reply && (
          <li className="msg msg-agent">
            <Avatar member={author} size="sm" />
            <div className="msg-body">
              <p className="msg-head">{author && <CrewName id={author.id}>{author.name}</CrewName>}</p>
              <div className="bubble bubble-agent">
                <Markdown>{reply.text}</Markdown>
              </div>
              {reply.cards.map((card, i) => (
                <Card key={i} card={card} busy={false} onAction={() => {}} />
              ))}
            </div>
          </li>
        )}
      </ol>
    </section>
  )
}

const STEPS = [
  { title: 'Ask in plain words', body: 'Type a question, or tap one. “When will I be debt-free?” is a perfectly good start.' },
  { title: 'The right friend works it out', body: 'Finbo hands it to whoever knows best. Every sum is done by tested code, and prices come live from the market.' },
  { title: 'Every figure is checked', body: 'Before you see an answer, each number in it is traced back to a calculation. Personal details never reach the AI.' },
  { title: 'Nothing happens until you say yes', body: 'Plans wait for your approval. What you decide is kept in one place, on the web or in Telegram.' },
]

export function Landing() {
  const { list } = useCrew()
  const [health, setHealth] = useState<Health | null>(null)

  useEffect(() => {
    publicApi.health().then(setHealth).catch(() => setHealth(null))
  }, [])

  return (
    <>
      <section className="hero" aria-labelledby="hero-title">
        <div className="hero-copy">
          <h1 id="hero-title" className="hero-title">
            Your money, explained by a friendly crew.
          </h1>
          <p className="hero-sub">
            Finbo the fox and five animal friends look at your spending, savings, debts and the
            markets, answer in plain words, and only act when you say yes. For India and the US.
          </p>
          <div className="hero-actions">
            <Link className="btn btn-primary btn-large" to="/sign-up">
              Create your free account
            </Link>
            <a className="btn btn-soft btn-large" href="#demo">
              See a real answer
            </a>
          </div>
        </div>
        <ul className="hero-crew" aria-label="The crew">
          {list.map((m) => (
            <li key={m.id} className={`hero-member crew-${m.id}`}>
              <Avatar member={m} size="xl" />
              <span className="hero-member-name">{m.name}</span>
            </li>
          ))}
        </ul>
      </section>

      <Demo />

      <section className="crew-section" aria-labelledby="crew-title">
        <h2 id="crew-title" className="section-title">
          Meet the crew
        </h2>
        <p className="section-sub">Each friend has one job, so you always know who to ask.</p>
        <ul className="crew-grid">
          {list.map((m) => (
            <li key={m.id} className={`crew-card crew-${m.id}`}>
              <Avatar member={m} size="lg" />
              <h3>
                <CrewName id={m.id}>{m.name}</CrewName>{' '}
                <span className="muted">the {m.animal}</span>
              </h3>
              <p className="crew-card-role">{m.role}</p>
              <p>{m.helps_with}</p>
              <p className="crew-card-ask">“{m.quick_actions[0]?.label}”</p>
            </li>
          ))}
        </ul>
      </section>

      <section className="steps-section" aria-labelledby="steps-title">
        <h2 id="steps-title" className="section-title">
          How it works
        </h2>
        <ol className="steps">
          {STEPS.map((s) => (
            <li key={s.title}>
              <h3>{s.title}</h3>
              <p>{s.body}</p>
            </li>
          ))}
        </ol>
      </section>

      <section className="telegram-section" aria-labelledby="tg-title">
        <div>
          <h2 id="tg-title" className="section-title">
            Chat with the crew in Telegram too
          </h2>
          <p>
            One bot, the whole crew. Send <code>/snowy when am I debt-free?</code> or{' '}
            <code>/bruno RELIANCE</code>, tap the buttons to approve plans, and send your statement
            as a CSV. Link it to your account and both places share the same numbers.
          </p>
        </div>
        {health?.telegram.configured && health.telegram.url ? (
          <a className="btn btn-primary btn-large" href={health.telegram.url} target="_blank" rel="noopener noreferrer">
            Open Finbo in Telegram
          </a>
        ) : (
          <p className="muted">The Telegram bot isn’t connected on this server yet.</p>
        )}
      </section>

      <section className="limits" aria-labelledby="limits-title">
        <h2 id="limits-title" className="section-title">
          What Finbo won’t do
        </h2>
        <ul className="limits-list">
          <li>It won’t move money or connect to your bank. You upload a CSV export of your statement.</li>
          <li>It won’t tell you to buy or sell a stock. It explains prices and risk, and stops there.</li>
          <li>
            It isn’t regulated advice. Personalised investment advice needs SEBI registration in
            India or SEC registration in the US, and this project has neither.
          </li>
          <li>Free-form chat needs an AI key on the server. Every quick question works without one.</li>
        </ul>
        <Link className="btn btn-primary btn-large" to="/sign-up">
          Create your free account
        </Link>
      </section>
    </>
  )
}
