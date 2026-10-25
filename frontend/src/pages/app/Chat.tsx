import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router'
import { Message, Typing } from '../../components/chat/Message'
import { Composer } from '../../components/chat/Composer'
import { Avatar, CrewName } from '../../components/Crew'
import { MoneyPanel } from '../../components/MoneyPanel'
import { ErrorState, LoadingState } from '../../components/States'
import { publicApi, type ChatMessage, type CrewId, type QuickAction } from '../../lib/api'
import { useCrew } from '../../lib/crew'
import { useReadyWorkspace } from '../../lib/workspace'

const IDS: CrewId[] = ['finbo', 'penny', 'hazel', 'snowy', 'bruno', 'scout']

function preview(msg?: ChatMessage): string {
  if (!msg) return 'Say hello'
  const text = msg.text.replace(/\s+/g, ' ')
  return (msg.role === 'user' ? 'You: ' : '') + (text.length > 48 ? `${text.slice(0, 47)}…` : text)
}

function CrewRail({
  active,
  latest,
}: {
  active: CrewId
  latest: Partial<Record<CrewId, ChatMessage>>
}) {
  const { list } = useCrew()
  return (
    <nav className="crew-rail" aria-label="Your crew">
      <h2 className="panel-title rail-title">Your crew</h2>
      <ul>
        {list.map((m) => (
          <li key={m.id}>
            <Link
              to={`/app/chat/${m.id}`}
              className="rail-item"
              aria-current={m.id === active ? 'page' : undefined}
            >
              <Avatar member={m} size="md" />
              <span className="rail-text">
                <span className="rail-name">{m.name}</span>
                <span className="rail-role">{m.role}</span>
                <span className="rail-preview">{preview(latest[m.id])}</span>
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  )
}

// Shown straight away while the crew works; replaced by the stored copy when the reply lands.
const mine = (thread: CrewId, text: string): ChatMessage => ({
  id: -Date.now(),
  thread,
  role: 'user',
  author: 'you',
  text,
  cards: [],
  meta: {},
  channel: 'web',
  created_at: new Date().toISOString(),
})

export function Chat() {
  const params = useParams()
  const thread: CrewId = IDS.includes(params.crewId as CrewId) ? (params.crewId as CrewId) : 'finbo'
  const [search, setSearch] = useSearchParams()
  const navigate = useNavigate()
  const { api, reload } = useReadyWorkspace()
  const { byId, error: crewError } = useCrew()
  const member = byId[thread]

  const [messages, setMessages] = useState<ChatMessage[] | null>(null)
  const [latest, setLatest] = useState<Partial<Record<CrewId, ChatMessage>>>({})
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [aiReady, setAiReady] = useState<boolean | null>(null)
  const list = useRef<HTMLOListElement>(null)
  const askedFor = useRef<string | null>(null)

  const refreshLatest = useCallback(() => {
    api.chats().then(setLatest).catch(() => {})
  }, [api])

  useEffect(() => {
    publicApi
      .health()
      .then((h) => setAiReady(h.providers.some((p) => p.configured)))
      .catch(() => setAiReady(null))
    refreshLatest()
  }, [refreshLatest])

  // Switching crew member clears the old conversation before the new one loads.
  const [shownThread, setShownThread] = useState(thread)
  if (shownThread !== thread) {
    setShownThread(thread)
    setMessages(null)
    setError(null)
  }

  useEffect(() => {
    let cancelled = false
    api
      .chat(thread)
      .then((m) => !cancelled && setMessages(m))
      .catch((e: Error) => !cancelled && setError(e.message))
    return () => {
      cancelled = true
    }
  }, [api, thread])

  useEffect(() => {
    // Scroll the list itself: scrollIntoView would also move the keyboard's Tab starting point.
    const el = list.current
    el?.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
  }, [messages, busy])

  const run = useCallback(
    async (work: () => Promise<ChatMessage[]>, optimistic?: ChatMessage, refetch = false) => {
      setBusy(true)
      setError(null)
      if (optimistic) setMessages((m) => [...(m ?? []), optimistic])
      try {
        const added = await work()
        if (refetch) {
          setMessages(await api.chat(thread))
        } else {
          setMessages((m) => [...(m ?? []).filter((x) => x.id !== optimistic?.id), ...added])
        }
        refreshLatest()
      } catch (e) {
        setMessages((m) => (m ?? []).filter((x) => x.id !== optimistic?.id))
        setError(e instanceof Error ? e.message : 'That didn’t go through. Try again.')
      } finally {
        setBusy(false)
      }
    },
    [api, thread, refreshLatest],
  )

  const send = (text: string) => run(() => api.send(thread, text), mine(thread, text))

  const quick = useCallback(
    (action: QuickAction | string, arg?: string) => {
      const id = typeof action === 'string' ? action : action.id
      const label = member?.quick_actions.find((a) => a.id === id)?.label
      const shown = label && (arg ? `${label}: ${arg}` : label)
      return run(() => api.quick(thread, id, arg), shown ? mine(thread, shown) : undefined)
    },
    [api, thread, run, member],
  )

  const act = (msg: ChatMessage, card: number, action: number) => {
    const spec = msg.cards[card].actions[action]
    if (spec.kind === 'quick' && spec.payload.agent !== thread) {
      // A button that hands over to another crew member: go to their chat and ask there.
      const q = new URLSearchParams({ ask: String(spec.payload.action) })
      if (spec.payload.arg) q.set('arg', String(spec.payload.arg))
      navigate(`/app/chat/${spec.payload.agent}?${q}`)
      return
    }
    void run(async () => {
      const added = await api.act(msg.id, card, action)
      reload() // approvals and filing change the numbers elsewhere
      return added
    }, undefined, true)
  }

  // Arriving from the money panel or another crew member with ?ask=...: ask it once.
  useEffect(() => {
    const ask = search.get('ask')
    if (!ask || messages === null || askedFor.current === `${thread}:${ask}`) return
    askedFor.current = `${thread}:${ask}`
    const arg = search.get('arg') ?? undefined
    setSearch({}, { replace: true })
    void quick(ask, arg)
  }, [search, messages, thread, quick, setSearch])

  if (crewError) return <ErrorState message={crewError} />
  if (!member) return <LoadingState what="Getting the crew together" />

  return (
    <div className="chat-layout">
      <CrewRail active={thread} latest={latest} />

      <section className="thread" aria-labelledby="thread-title">
        <header className="thread-head">
          <Avatar member={member} size="lg" />
          <div>
            <h1 id="thread-title" className="thread-name">
              <CrewName id={member.id}>{member.name}</CrewName>
            </h1>
            <p className="thread-role">{member.helps_with}</p>
          </div>
        </header>

        <ol ref={list} className="messages" aria-live="polite">
          <li className="msg msg-agent">
            <Avatar member={member} size="sm" />
            <div className="msg-body">
              <p className="msg-head">
                <CrewName id={member.id}>{member.name}</CrewName>
              </p>
              <div className="bubble bubble-agent">
                <p>{member.greeting}</p>
              </div>
            </div>
          </li>
          {messages === null && !error && (
            <li>
              <LoadingState what="Loading your conversation" />
            </li>
          )}
          {messages?.map((m) => <Message key={m.id} msg={m} busy={busy} onAction={act} />)}
          {busy && <Typing member={member} />}
          {error && (
            <li>
              <ErrorState message={error} />
            </li>
          )}
        </ol>

        <Composer member={member} busy={busy} aiReady={aiReady} onSend={send} onQuick={quick} />
      </section>

      <MoneyPanel />
    </div>
  )
}
