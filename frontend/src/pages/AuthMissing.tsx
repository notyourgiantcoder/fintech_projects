import { Link } from 'react-router'
import { Wordmark } from '../components/Wordmark'

/** Shown when no Clerk key is configured, instead of a broken sign-in. */
export function AuthMissing() {
  return (
    <div className="standalone">
      <Wordmark />
      <h1 className="standalone-title">Sign-in isn’t set up on this server yet</h1>
      <p>Finbo uses Clerk for accounts. To turn it on:</p>
      <ol className="steps-plain">
        <li>
          Create a free application at <a href="https://dashboard.clerk.com">dashboard.clerk.com</a>{' '}
          and copy its publishable key (it starts with <code>pk_</code>).
        </li>
        <li>
          In the project’s <code>.env</code>, set both <code>VITE_CLERK_PUBLISHABLE_KEY</code> and{' '}
          <code>CLERK_PUBLISHABLE_KEY</code> to that key.
        </li>
        <li>Restart the API server and the Bun dev server.</li>
      </ol>
      <p>
        <Link to="/">Back to the home page</Link>
      </p>
    </div>
  )
}
