import { Link } from 'react-router'

/** The product name set in type. No logo exists yet, so none is invented. */
export function Wordmark({ to = '/' }: { to?: string }) {
  return (
    <Link to={to} className="wordmark" aria-label="Finbo home">
      finbo
    </Link>
  )
}
