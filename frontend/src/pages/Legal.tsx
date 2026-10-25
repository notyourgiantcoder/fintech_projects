import { Link } from 'react-router'

export function Privacy() {
  return (
    <article className="prose-page">
      <h1 className="section-title">Privacy</h1>
      <p className="muted">How this deployment of Finbo handles your data.</p>
      <h2>Your account</h2>
      <p>
        Sign-in is provided by Clerk. Clerk stores your email address and sign-in details under its
        own privacy policy. Finbo receives a signed token that identifies your account and
        nothing else.
      </p>
      <h2>Your financial data</h2>
      <p>
        Statements you upload, the income and debts you enter, your decisions and your activity
        log are stored in Finbo’s database, linked to your account. They stay until you delete
        them from <Link to="/app/settings">Settings</Link>, which removes all of them at once.
      </p>
      <h2>Questions you ask</h2>
      <p>
        Before a question leaves Finbo, identifiers such as PAN, Aadhaar, card, account and
        phone numbers and email addresses are replaced with placeholders. That redacted question,
        plus the calculation results needed to answer it, is sent to the language model provider
        configured on the server (GitHub Models or Google Gemini), and the redacted question is
        what your activity log keeps. Some free tiers, including Gemini’s, may use requests to
        improve the provider’s products, so use sample data rather than real statements on a
        public deployment.
      </p>
      <h2>Market data and research</h2>
      <p>
        When you look up a stock or the AI researches one, the ticker or company name is sent to
        Yahoo Finance, Google News, SEC EDGAR or HackerNews. None of your own financial data is
        sent to them.
      </p>
      <h2>OneDrive and SharePoint</h2>
      <p>
        If you connect a Microsoft account, Finbo uses the access Microsoft grants only to save
        or read its own workbook, for that one request. The token is not stored.
      </p>
      <h2>Contact</h2>
      <p>
        This is a portfolio project without a company behind it. Questions go to the project’s
        owner through the repository where you found it.
      </p>
    </article>
  )
}

export function Terms() {
  return (
    <article className="prose-page">
      <h1 className="section-title">Terms</h1>
      <p className="muted">The short version: this is a demo, use it to learn, not to invest.</p>
      <h2>Not financial advice</h2>
      <p>
        Finbo gives educational guidance only. It is not registered with SEBI, the SEC or any
        other regulator, and nothing it shows is a recommendation to buy, sell or borrow.
      </p>
      <h2>No guarantees</h2>
      <p>
        The calculations assume interest rates and minimum payments stay constant and that you
        take on no new debt. Real lenders compound and charge fees in ways this model may not
        capture. Market prices are delayed and come from an unofficial source. Check important
        numbers with your lender or broker.
      </p>
      <h2>Availability</h2>
      <p>
        The service can stop, restart or lose data at any time. See the{' '}
        <Link to="/privacy">privacy page</Link> for what is stored.
      </p>
    </article>
  )
}

export function NotFound() {
  return (
    <div className="standalone">
      <h1 className="standalone-title">There’s no page at this address</h1>
      <p>
        The link may be mistyped or out of date. Go to the <Link to="/">home page</Link> or{' '}
        <Link to="/app">your workspace</Link>.
      </p>
    </div>
  )
}
