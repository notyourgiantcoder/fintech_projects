import { UserButton } from '@clerk/react'
import type { ReactNode } from 'react'
import { Link, Navigate, NavLink, Outlet, useLocation } from 'react-router'
import { ErrorState, LoadingState } from '../components/States'
import { ThemeToggle } from '../components/ThemeToggle'
import { Wordmark } from '../components/Wordmark'
import { useAppAuth } from '../lib/auth'
import { useWorkspace, WorkspaceProvider } from '../lib/workspace'
import { AuthMissing } from '../pages/AuthMissing'

// Five places, in the order people need them. Each is owned by someone in the crew.
const NAV = [
  { to: '/app', label: 'Chat', end: false, match: /^\/app(\/chat.*)?$/ },
  { to: '/app/money', label: 'Money' },
  { to: '/app/markets', label: 'Markets' },
  { to: '/app/plans', label: 'Plans' },
  { to: '/app/settings', label: 'Settings' },
]

export function AppLayout() {
  const auth = useAppAuth()
  if (auth.mode === 'missing') return <AuthMissing />
  if (!auth.isLoaded) return <LoadingState what="Checking your sign-in" />
  if (!auth.isSignedIn) return <Navigate to="/sign-in" replace />
  return (
    <WorkspaceProvider>
      <AppShell />
    </WorkspaceProvider>
  )
}

function Account() {
  const { mode, displayName } = useAppAuth()
  if (mode === 'clerk') return <UserButton />
  return <span className="account-dev">{displayName}</span>
}

function NavItems({ className }: { className: string }) {
  const { pathname } = useLocation()
  return (
    <>
      {NAV.map((item) => {
        const chat = item.match?.test(pathname)
        return (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.match ? false : undefined}
            className={({ isActive }) =>
              `${className}${(item.match ? chat : isActive) ? ' is-active' : ''}`
            }
            aria-current={(item.match ? chat : undefined) ? 'page' : undefined}
          >
            {item.label}
          </NavLink>
        )
      })}
    </>
  )
}

function AppShell() {
  const { mode } = useAppAuth()
  const { pathname } = useLocation()
  const chatPage = /^\/app(\/chat.*)?$/.test(pathname)
  return (
    <div className="app">
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      {mode === 'dev' && (
        <p className="dev-banner">
          Dev mode: sign-in is off and everyone shares one space. Set VITE_CLERK_PUBLISHABLE_KEY to
          use Clerk.
        </p>
      )}
      <header className="topbar">
        <Wordmark to="/app" />
        <nav className="topnav" aria-label="Main">
          <NavItems className="topnav-link" />
        </nav>
        <div className="topbar-end">
          <ThemeToggle className="icon-button" />
          <Account />
        </div>
      </header>
      <main id="main" className={chatPage ? 'main main-chat' : 'main'}>
        <WorkspaceGate>
          <Outlet />
        </WorkspaceGate>
      </main>
      <nav className="tabbar" aria-label="Main">
        <NavItems className="tab" />
      </nav>
    </div>
  )
}

function WorkspaceGate({ children }: { children: ReactNode }) {
  const ws = useWorkspace()
  const { pathname } = useLocation()
  const onWelcome = pathname === '/app/welcome'

  if (ws.status === 'not_set_up' && !onWelcome) return <Navigate to="/app/welcome" replace />
  if (onWelcome) return children
  if (!ws.data && ws.status === 'error') {
    return (
      <ErrorState message={ws.error ?? 'Your space didn’t load.'}>
        <p>
          Check that the server is running, then{' '}
          <button className="link-button" onClick={ws.reload}>
            try again
          </button>
          . If it keeps failing, <Link to="/">go back to the home page</Link>.
        </p>
      </ErrorState>
    )
  }
  if (!ws.data) return <LoadingState what="Loading your numbers" />
  return children
}
