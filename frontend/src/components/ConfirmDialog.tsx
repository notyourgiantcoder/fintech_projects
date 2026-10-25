import { useEffect, useRef, type ReactNode } from 'react'

interface Props {
  open: boolean
  title: string
  confirmLabel: string
  busy?: boolean
  onConfirm: () => void
  onClose: () => void
  children: ReactNode
}

/** Native <dialog>: focus is trapped and Escape closes it. */
export function ConfirmDialog({ open, title, confirmLabel, busy, onConfirm, onClose, children }: Props) {
  const ref = useRef<HTMLDialogElement>(null)

  useEffect(() => {
    const dialog = ref.current
    if (!dialog) return
    if (open && !dialog.open) dialog.showModal()
    if (!open && dialog.open) dialog.close()
  }, [open])

  return (
    <dialog ref={ref} className="dialog" onClose={onClose} aria-labelledby="dialog-title">
      <h2 id="dialog-title">{title}</h2>
      <div className="dialog-body">{children}</div>
      <div className="dialog-actions">
        <button className="btn btn-danger" disabled={busy} onClick={onConfirm}>
          {confirmLabel}
        </button>
        <button className="btn btn-ghost" onClick={onClose} autoFocus>
          Cancel
        </button>
      </div>
    </dialog>
  )
}
