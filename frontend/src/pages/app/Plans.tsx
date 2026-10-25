import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { Avatar } from '../../components/Crew'
import { ErrorState, LoadingState } from '../../components/States'
import type { ActivityEvent } from '../../lib/api'
import { useCrew } from '../../lib/crew'
import { useReadyWorkspace } from '../../lib/workspace'

const KIND_LABEL: Record<string, string> = {
  ask: 'You asked',
  refused: 'Not sent to the AI',
  setup: 'Started',
  upload: 'Uploaded a statement',
  excel_import: 'Imported from Excel',
  onedrive_push: 'Saved to OneDrive',
}

const SOURCE_LABEL: Record<string, string> = { app: 'in Finbo', excel: 'in Excel', telegram: 'on Telegram' }

function when(iso: string): string {
  return new Date(iso).toLocaleString('en-GB', {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function Activity() {
  const { api } = useReadyWorkspace()
  const [events, setEvents] = useState<ActivityEvent[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api
      .activity()
      .then(setEvents)
      .catch((e: Error) => setError(e.message))
  }, [api])

  return (
    <section className="plain-card" aria-labelledby="activity-title">
      <h2 id="activity-title" className="section-title">
        What’s happened
      </h2>
      <p className="muted">
        Uploads, imports and questions answered by the AI, newest first. Questions are stored with
        personal details already removed.
      </p>
      {error && <ErrorState message={error} />}
      {!error && events === null && <LoadingState what="Loading your activity" />}
      {events?.length === 0 && <p>Nothing yet. Ask the crew something and it shows up here.</p>}
      {events && events.length > 0 && (
        <ol className="history">
          {events.map((e) => (
            <li key={e.id}>
              <span className="history-when">{when(e.created_at)}</span>
              <span className="history-what">
                <strong>{KIND_LABEL[e.kind] ?? e.kind}</strong> {e.summary}
              </span>
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}

export function Plans() {
  const { data } = useReadyWorkspace()
  const { byId } = useCrew()
  const decisions = [...data.approvals].reverse()

  return (
    <div className="page">
      <header className="page-intro">
        <h1 className="page-title">Your plans</h1>
        <p className="page-sub">
          Nothing the crew suggests counts until you say yes. Here’s everything you’ve decided, in
          the app, in Excel or on Telegram.
        </p>
      </header>

      <section className="plain-card" aria-labelledby="decided-title">
        <div className="plain-card-head">
          <Avatar member={byId.finbo} size="md" />
          <h2 id="decided-title" className="section-title">
            Decided
          </h2>
        </div>
        {decisions.length === 0 ? (
          <div className="empty">
            <p>You haven’t approved any plans yet.</p>
            <Link className="btn btn-primary" to="/app/chat/snowy?ask=debt_free">
              Look at Snowy’s debt plan
            </Link>
          </div>
        ) : (
          <ul className="decisions">
            {decisions.map((a) => (
              <li key={a.id}>
                <span className={a.decision === 'approved' ? 'badge badge-yes' : 'badge'}>
                  {a.decision === 'approved' ? 'Approved' : 'Sent back'}
                </span>
                <span className="decision-text">{a.subject}</span>
                <span className="muted decision-meta">
                  {when(a.decided_at)} {SOURCE_LABEL[a.source] ?? ''}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <Activity />
    </div>
  )
}
