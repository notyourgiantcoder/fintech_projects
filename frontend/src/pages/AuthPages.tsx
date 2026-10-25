import { SignIn, SignUp } from '@clerk/react'
import type { ReactNode } from 'react'
import { Link, Navigate } from 'react-router'
import { Wordmark } from '../components/Wordmark'
import { useAppAuth } from '../lib/auth'
import { AuthMissing } from './AuthMissing'

function AuthFrame({ aside, children }: { aside: string; children: ReactNode }) {
  return (
    <div className="auth">
      <aside className="auth-aside">
        <Wordmark />
        <p className="auth-aside-line">{aside}</p>
      </aside>
      <main id="main" className="auth-main">
        {children}
      </main>
    </div>
  )
}

function Gate({ children }: { children: ReactNode }) {
  const { mode } = useAppAuth()
  if (mode === 'missing') return <AuthMissing />
  if (mode === 'dev') return <Navigate to="/app" replace />
  return children
}

export function SignInPage() {
  return (
    <Gate>
      <AuthFrame aside="Your plans, your decision log and your numbers are waiting where you left them.">
        <SignIn routing="path" path="/sign-in" signUpUrl="/sign-up" fallbackRedirectUrl="/app" />
        <p className="auth-alt">
          New here? <Link to="/sign-up">Create an account</Link>
        </p>
      </AuthFrame>
    </Gate>
  )
}

export function SignUpPage() {
  return (
    <Gate>
      <AuthFrame aside="Start on sample data for India or the US, then swap in your own statement when you’re ready.">
        <SignUp routing="path" path="/sign-up" signInUrl="/sign-in" fallbackRedirectUrl="/app" />
        <p className="auth-alt">
          Already have an account? <Link to="/sign-in">Sign in</Link>
        </p>
      </AuthFrame>
    </Gate>
  )
}
