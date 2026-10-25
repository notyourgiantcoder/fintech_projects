import { ClerkProvider, useAuth, useClerk, useUser, type ClerkProviderProps } from '@clerk/react'
import { createContext, useContext, useMemo, type ReactNode } from 'react'
import { useNavigate } from 'react-router'
import { useTheme, type Theme } from './theme'

// Three modes: Clerk (the real thing), dev (explicit VITE_DEV_AUTH=1, no sign-in, local
// only) and missing (no key yet: the app explains how to add one instead of crashing).
export type AuthMode = 'clerk' | 'dev' | 'missing'

export interface AppAuth {
  mode: AuthMode
  isLoaded: boolean
  isSignedIn: boolean
  displayName: string | null
  getToken: () => Promise<string | null>
  signOut: () => Promise<void>
}

const PUBLISHABLE_KEY = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY as string | undefined
const DEV_AUTH = import.meta.env.VITE_DEV_AUTH === '1'

const noToken = async () => null
const noop = async () => {}

const AuthContext = createContext<AppAuth>({
  mode: 'missing',
  isLoaded: true,
  isSignedIn: false,
  displayName: null,
  getToken: noToken,
  signOut: noop,
})

function clerkAppearance(theme: Theme): ClerkProviderProps['appearance'] {
  const dark = theme === 'dark'
  return {
    variables: {
      colorPrimary: dark ? '#6FCF9F' : '#0C3B2E',
      colorPrimaryForeground: dark ? '#0E1713' : '#FAFAF7',
      colorBackground: dark ? '#14211B' : '#FFFFFF',
      colorForeground: dark ? '#EEF2EC' : '#0D1B14',
      colorMutedForeground: dark ? '#A3B3AA' : '#4A5A51',
      colorInput: dark ? '#0E1713' : '#FAFAF7',
      colorInputForeground: dark ? '#EEF2EC' : '#0D1B14',
      colorDanger: dark ? '#FFB4A8' : '#B42318',
      fontFamily: "'Schibsted Grotesk', system-ui, sans-serif",
      borderRadius: '6px',
    },
  }
}

function ClerkBridge({ children }: { children: ReactNode }) {
  const { isLoaded, isSignedIn, getToken } = useAuth()
  const { user } = useUser()
  const clerk = useClerk()
  const value = useMemo<AppAuth>(
    () => ({
      mode: 'clerk',
      isLoaded,
      isSignedIn: Boolean(isSignedIn),
      displayName: user?.firstName ?? user?.primaryEmailAddress?.emailAddress ?? null,
      getToken: () => getToken(),
      signOut: () => clerk.signOut({ redirectUrl: '/' }),
    }),
    [isLoaded, isSignedIn, getToken, user, clerk],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function AppAuthProvider({ children }: { children: ReactNode }) {
  const navigate = useNavigate()
  const { theme } = useTheme()

  if (PUBLISHABLE_KEY) {
    return (
      <ClerkProvider
        publishableKey={PUBLISHABLE_KEY}
        routerPush={(to) => navigate(to)}
        routerReplace={(to) => navigate(to, { replace: true })}
        signInUrl="/sign-in"
        signUpUrl="/sign-up"
        afterSignOutUrl="/"
        appearance={clerkAppearance(theme)}
      >
        <ClerkBridge>{children}</ClerkBridge>
      </ClerkProvider>
    )
  }

  const value: AppAuth = DEV_AUTH
    ? {
        mode: 'dev',
        isLoaded: true,
        isSignedIn: true,
        displayName: 'Dev user',
        getToken: noToken,
        signOut: async () => navigate('/'),
      }
    : {
        mode: 'missing',
        isLoaded: true,
        isSignedIn: false,
        displayName: null,
        getToken: noToken,
        signOut: noop,
      }
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export const useAppAuth = () => useContext(AuthContext)
