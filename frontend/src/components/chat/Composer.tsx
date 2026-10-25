import { useRef, useState, type FormEvent } from 'react'
import type { CrewMember, QuickAction } from '../../lib/api'

interface Props {
  member: CrewMember
  busy: boolean
  aiReady: boolean | null
  onSend: (text: string) => void
  onQuick: (action: QuickAction, arg?: string) => void
}

const ASK_FOR: Record<'symbol' | 'topic', { prompt: string; placeholder: string }> = {
  symbol: { prompt: 'Which stock or index?', placeholder: 'RELIANCE, TCS, AAPL or ^NSEI' },
  topic: { prompt: 'News about what?', placeholder: 'A company or topic, like Infosys' },
}

export function Composer({ member, busy, aiReady, onSend, onQuick }: Props) {
  const [text, setText] = useState('')
  const [asking, setAsking] = useState<QuickAction | null>(null)
  const [arg, setArg] = useState('')
  const box = useRef<HTMLTextAreaElement>(null)

  function submit(e?: FormEvent) {
    e?.preventDefault()
    if (busy) return
    if (asking) {
      if (!arg.trim()) return
      onQuick(asking, arg.trim())
      setAsking(null)
      setArg('')
      return
    }
    if (!text.trim()) return
    onSend(text.trim())
    setText('')
  }

  return (
    <div className="composer">
      <div className="chips" role="group" aria-label={`Quick questions for ${member.name}`}>
        {member.quick_actions.map((a) => (
          <button
            key={a.id}
            type="button"
            className="chip"
            disabled={busy}
            aria-pressed={asking?.id === a.id}
            onClick={() => (a.needs ? setAsking(a) : onQuick(a))}
          >
            {a.label}
          </button>
        ))}
      </div>
      <form className="composer-box" onSubmit={submit}>
        {asking?.needs ? (
          <>
            <label htmlFor="composer-arg" className="composer-prompt">
              {ASK_FOR[asking.needs].prompt}
            </label>
            <input
              id="composer-arg"
              className="composer-input"
              autoFocus
              autoComplete="off"
              placeholder={ASK_FOR[asking.needs].placeholder}
              value={arg}
              onChange={(e) => setArg(e.target.value)}
              onKeyDown={(e) => e.key === 'Escape' && setAsking(null)}
            />
            <button type="button" className="btn btn-soft" onClick={() => setAsking(null)}>
              Cancel
            </button>
          </>
        ) : (
          <>
            <label htmlFor="composer-text" className="visually-hidden">
              Message {member.name}
            </label>
            <textarea
              id="composer-text"
              ref={box}
              className="composer-input"
              rows={1}
              placeholder={`Message ${member.name}`}
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  submit()
                }
              }}
            />
          </>
        )}
        <button type="submit" className="send" disabled={busy || (asking ? !arg.trim() : !text.trim())}>
          Send
        </button>
      </form>
      {aiReady === false && (
        <p className="composer-hint">
          Quick questions always work. Free typing gets the closest quick answer until an AI key is
          added on the server.
        </p>
      )}
    </div>
  )
}
