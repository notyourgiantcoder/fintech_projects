import Markdown from 'react-markdown'
import type { ChatMessage, CrewMember } from '../../lib/api'
import { useCrew } from '../../lib/crew'
import { Avatar, CrewName } from '../Crew'
import { Card } from './Cards'

function when(iso: string): string {
  return new Date(iso).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })
}

function Checks({ msg }: { msg: ChatMessage }) {
  const checks = msg.meta.checks
  if (msg.meta.mode !== 'ai' || !checks) return null
  if (checks.unverified_figures.length) {
    return (
      <p className="msg-check msg-check-warn">
        Double-check {checks.unverified_figures.join(', ')}: I couldn’t trace{' '}
        {checks.unverified_figures.length === 1 ? 'it' : 'them'} to a calculation.
      </p>
    )
  }
  const redacted = Object.keys(checks.pii_redacted).length
  return (
    <p className="msg-check">
      {checks.figures_checked > 0
        ? `All ${checks.figures_checked} figures checked against the calculator.`
        : 'Answered from your data.'}
      {redacted ? ' Personal details were removed before the AI saw your question.' : ''}
    </p>
  )
}

export function Message({
  msg,
  busy,
  onAction,
}: {
  msg: ChatMessage
  busy: boolean
  onAction: (msg: ChatMessage, card: number, action: number) => void
}) {
  const { byId } = useCrew()
  if (msg.role === 'user') {
    return (
      <li className="msg msg-user">
        <div className="bubble bubble-user">{msg.text}</div>
        <span className="msg-time">{when(msg.created_at)}</span>
      </li>
    )
  }
  const author = byId[msg.author as keyof typeof byId] as CrewMember | undefined
  const helpers = (msg.meta.contributors ?? []).map((c) => byId[c]?.name).filter(Boolean)
  return (
    <li className="msg msg-agent">
      <Avatar member={author} size="sm" />
      <div className="msg-body">
        <p className="msg-head">
          {author && <CrewName id={author.id}>{author.name}</CrewName>}
          {helpers.length > 0 && <span className="muted"> with {helpers.join(' and ')}</span>}
          <span className="msg-time">{when(msg.created_at)}</span>
        </p>
        {msg.meta.note && <p className="msg-note">{msg.meta.note}</p>}
        <div className="bubble bubble-agent">
          <Markdown>{msg.text}</Markdown>
        </div>
        <Checks msg={msg} />
        {msg.cards.map((card, i) => (
          <Card key={i} card={card} busy={busy} onAction={(a) => onAction(msg, i, a)} />
        ))}
      </div>
    </li>
  )
}

export function Typing({ member }: { member?: CrewMember }) {
  return (
    <li className="msg msg-agent" aria-live="polite">
      <Avatar member={member} size="sm" />
      <div className="msg-body">
        <p className="msg-head">{member && <CrewName id={member.id}>{member.name}</CrewName>}</p>
        <div className="bubble bubble-agent typing" role="status">
          <span className="visually-hidden">{member?.name ?? 'Finbo'} is working it out</span>
          <span className="dot" aria-hidden="true" />
          <span className="dot" aria-hidden="true" />
          <span className="dot" aria-hidden="true" />
        </div>
      </div>
    </li>
  )
}
