import { useState } from 'react'
import type { Approval } from '../lib/api'
import { useReadyWorkspace } from '../lib/workspace'

interface Props {
  /** What the person is signing off, in their terms. */
  subject: string
  onDecide: (decision: Approval['decision']) => Promise<Approval>
}

export function ApprovalSlip({ subject, onDecide }: Props) {
  const { data } = useReadyWorkspace()
  // A plan already decided here, in chat or on Telegram shows that decision instead of asking twice.
  const earlier = data.approvals.findLast((a) => a.subject === subject) ?? null
  const [decided, setDecided] = useState<Approval | null>(null)
  const [reopened, setReopened] = useState(false)
  const shown = decided ?? (reopened ? null : earlier)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function decide(decision: Approval['decision']) {
    setBusy(true)
    setError(null)
    try {
      setDecided(await onDecide(decision))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Your decision wasn’t saved. Try again.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="slip">
      <p className="slip-subject">{subject}</p>
      {shown ? (
        <div className="row-actions">
          <p className="outcome" role="status">
            {shown.decision === 'approved' ? 'Approved' : 'Sent back'}
          </p>
          {!decided && (
            <button type="button" className="link-button" onClick={() => setReopened(true)}>
              Decide again
            </button>
          )}
        </div>
      ) : (
        <div className="card-actions">
          <button className="btn btn-accent" disabled={busy} onClick={() => decide('approved')}>
            Approve this plan
          </button>
          <button className="btn btn-soft" disabled={busy} onClick={() => decide('sent_back')}>
            Not now
          </button>
        </div>
      )}
      {error && (
        <p className="field-error" role="alert">
          {error}
        </p>
      )}
    </div>
  )
}
