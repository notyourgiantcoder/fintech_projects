import type { ReactNode } from 'react'

export function LoadingState({ what }: { what: string }) {
  return (
    <div className="state state-loading" role="status" aria-live="polite">
      <span className="state-bar" aria-hidden="true" />
      <p>{what}</p>
    </div>
  )
}

export function ErrorState({ message, children }: { message: string; children?: ReactNode }) {
  return (
    <div className="state state-error" role="alert">
      <p className="state-title">{message}</p>
      {children}
    </div>
  )
}

export function Notice({ children }: { children: ReactNode }) {
  return (
    <div className="notice" role="note">
      {children}
    </div>
  )
}
