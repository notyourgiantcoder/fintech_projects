import { Link, Outlet } from 'react-router'
import { ThemeToggle } from '../components/ThemeToggle'
import { Wordmark } from '../components/Wordmark'
import { useAppAuth } from '../lib/auth'

export function PublicLayout() {
  const { isSignedIn } = useAppAuth()
  return (
    <div className="public">
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <header className="topbar topbar-public">
        <Wordmark />
        <nav className="public-nav" aria-label="Site">
          <ThemeToggle className="icon-button" />
          {isSignedIn ? (
            <Link className="btn btn-primary" to="/app">
              Open Finbo
            </Link>
          ) : (
            <>
              <Link className="btn btn-ghost" to="/sign-in">
                Sign in
              </Link>
              <Link className="btn btn-primary" to="/sign-up">
                Create account
              </Link>
            </>
          )}
        </nav>
      </header>
      <main id="main">
        <Outlet />
      </main>
      <footer className="site-footer">
        <p>Finbo is a portfolio project. It gives educational guidance, not regulated advice.</p>
        <nav aria-label="Legal">
          <Link to="/privacy">Privacy</Link>
          <Link to="/terms">Terms</Link>
        </nav>
      </footer>
    </div>
  )
}
