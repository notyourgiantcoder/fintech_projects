import { lazy, Suspense, type ReactNode } from 'react'
import { Navigate, Route, Routes } from 'react-router'
import { LoadingState } from './components/States'
import { PublicLayout } from './layouts/PublicLayout'
import { SignInPage, SignUpPage } from './pages/AuthPages'
import { Landing } from './pages/Landing'
import { NotFound, Privacy, Terms } from './pages/Legal'

// Signed-in pages load on demand so the public landing page stays light.
const AppLayout = lazy(() => import('./layouts/AppLayout').then((m) => ({ default: m.AppLayout })))
const Chat = lazy(() => import('./pages/app/Chat').then((m) => ({ default: m.Chat })))
const Welcome = lazy(() => import('./pages/app/Welcome').then((m) => ({ default: m.Welcome })))
const Money = lazy(() => import('./pages/app/Money').then((m) => ({ default: m.Money })))
const Markets = lazy(() => import('./pages/app/Markets').then((m) => ({ default: m.Markets })))
const Plans = lazy(() => import('./pages/app/Plans').then((m) => ({ default: m.Plans })))
const Settings = lazy(() => import('./pages/app/Settings').then((m) => ({ default: m.Settings })))

const page = (node: ReactNode) => (
  <Suspense fallback={<LoadingState what="Opening the page" />}>{node}</Suspense>
)

export default function App() {
  return (
    <Routes>
      <Route element={<PublicLayout />}>
        <Route index element={<Landing />} />
        <Route path="privacy" element={<Privacy />} />
        <Route path="terms" element={<Terms />} />
      </Route>
      <Route path="sign-in/*" element={<SignInPage />} />
      <Route path="sign-up/*" element={<SignUpPage />} />
      <Route path="app" element={page(<AppLayout />)}>
        <Route index element={page(<Chat />)} />
        <Route path="chat/:crewId" element={page(<Chat />)} />
        <Route path="welcome" element={page(<Welcome />)} />
        <Route path="money" element={page(<Money />)} />
        <Route path="markets" element={page(<Markets />)} />
        <Route path="plans" element={page(<Plans />)} />
        <Route path="settings" element={page(<Settings />)} />
        {/* Old addresses from the first version */}
        <Route path="spending" element={<Navigate to="/app/money" replace />} />
        <Route path="safety-net" element={<Navigate to="/app/money" replace />} />
        <Route path="debt" element={<Navigate to="/app/money" replace />} />
        <Route path="ask" element={<Navigate to="/app" replace />} />
        <Route path="decisions" element={<Navigate to="/app/plans" replace />} />
        <Route path="*" element={<NotFound />} />
      </Route>
      <Route path="*" element={<NotFound />} />
    </Routes>
  )
}
