import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { ApiError, createApi, type Api, type Approval, type Market, type Workspace } from './api'
import { useAppAuth } from './auth'

// Debt plans start at minimum payments everywhere (chat, Telegram, Money) until the
// user chooses an extra amount, so every screen shows the same debt-free date.
const DEFAULT_EXTRA: Record<Market, number> = { in: 0, us: 0 }

type Status = 'loading' | 'ready' | 'not_set_up' | 'error'

interface WorkspaceState {
  api: Api
  status: Status
  error: string | null
  data: Workspace | null
  extra: number
  contribution: number | null
  setExtra: (value: number) => void
  setContribution: (value: number | null) => void
  /** Run a mutation that returns the new workspace, then refetch with current inputs. */
  mutate: (run: (api: Api) => Promise<Workspace>) => Promise<void>
  /** Start or restart from a country's sample data. */
  setup: (market: Market) => Promise<void>
  decide: (subject: string, decision: Approval['decision']) => Promise<Approval>
  reload: () => void
}

const WorkspaceContext = createContext<WorkspaceState | null>(null)

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const { getToken } = useAppAuth()
  const api = useMemo(() => createApi(getToken), [getToken])
  const [status, setStatus] = useState<Status>('loading')
  const [error, setError] = useState<string | null>(null)
  const [data, setData] = useState<Workspace | null>(null)
  const [extra, setExtra] = useState<number | null>(null)
  const [contribution, setContribution] = useState<number | null>(null)
  const [version, setVersion] = useState(0)

  useEffect(() => {
    let cancelled = false
    const timer = setTimeout(
      () => {
        api
          .me(extra ?? 0, contribution)
          .then((ws) => {
            if (cancelled) return
            if (extra === null) {
              // First load: start the payoff comparison with a sensible extra amount.
              setExtra(DEFAULT_EXTRA[ws.market])
            }
            setData(ws)
            setStatus('ready')
            setError(null)
          })
          .catch((e: unknown) => {
            if (cancelled) return
            if (e instanceof ApiError && e.status === 404) {
              setStatus('not_set_up')
            } else {
              setError(e instanceof Error ? e.message : 'Couldn’t load your workspace.')
              setStatus('error')
            }
          })
      },
      data ? 180 : 0,
    )
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
    // `data` only decides the debounce; refetching on it would loop.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [api, extra, contribution, version])

  const mutate = useCallback(
    async (run: (api: Api) => Promise<Workspace>) => {
      const ws = await run(api)
      setData(ws)
      setStatus('ready')
      setVersion((v) => v + 1)
    },
    [api],
  )

  const setup = useCallback(
    async (market: Market) => {
      setExtra(DEFAULT_EXTRA[market])
      setContribution(null)
      await mutate((a) => a.setup(market))
    },
    [mutate],
  )

  const decide = useCallback(
    async (subject: string, decision: Approval['decision']) => {
      const approval = await api.decide(subject, decision)
      setData((d) => (d ? { ...d, approvals: [...d.approvals, approval] } : d))
      return approval
    },
    [api],
  )

  const value: WorkspaceState = {
    api,
    status,
    error,
    data,
    extra: extra ?? 0,
    contribution,
    setExtra,
    setContribution,
    mutate,
    setup,
    decide,
    reload: () => setVersion((v) => v + 1),
  }
  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useWorkspace(): WorkspaceState {
  const ctx = useContext(WorkspaceContext)
  if (!ctx) throw new Error('useWorkspace must be used inside WorkspaceProvider')
  return ctx
}

/** For pages that render only once the workspace is ready. */
// eslint-disable-next-line react-refresh/only-export-components
export function useReadyWorkspace(): WorkspaceState & { data: Workspace } {
  const ws = useWorkspace()
  if (!ws.data) throw new Error('Workspace not loaded')
  return ws as WorkspaceState & { data: Workspace }
}
