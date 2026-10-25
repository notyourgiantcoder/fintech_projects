import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { publicApi, type CrewId, type CrewMember } from './api'

interface CrewState {
  list: CrewMember[]
  byId: Partial<Record<CrewId, CrewMember>>
  error: string | null
}

const CrewContext = createContext<CrewState>({ list: [], byId: {}, error: null })

/** The crew comes from the API (the same registry the Telegram bot uses). */
export function CrewProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<CrewState>({ list: [], byId: {}, error: null })

  useEffect(() => {
    publicApi
      .crew()
      .then((list) =>
        setState({ list, byId: Object.fromEntries(list.map((m) => [m.id, m])), error: null }),
      )
      .catch((e: Error) => setState((s) => ({ ...s, error: e.message })))
  }, [])

  return <CrewContext.Provider value={state}>{children}</CrewContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export const useCrew = () => useContext(CrewContext)
