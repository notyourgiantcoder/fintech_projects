import { useEffect, useRef, useState, type FormEvent } from 'react'
import { useLocation } from 'react-router'
import { ConfirmDialog } from '../../components/ConfirmDialog'
import { Notice } from '../../components/States'
import { ThemeToggle } from '../../components/ThemeToggle'
import {
  ApiError,
  publicApi,
  type DebtInput,
  type Market,
  type RowError,
  type TelegramCode,
  type TelegramStatus,
} from '../../lib/api'
import { sampleParts } from '../../lib/insights'
import { graphToken, MS_CLIENT_ID } from '../../lib/microsoft'
import { useReadyWorkspace } from '../../lib/workspace'

const TEMPLATE: Record<Market, string> = {
  in: 'Date,Category,Amount,Description\n01/11/2026,Rent,"₹22,000",Flat rent\n03/11/2026,Groceries,"₹4,350.50",Weekly groceries\n',
  us: 'Date,Category,Amount,Description\n2026-11-01,Rent,"$1,850.00",Apartment rent\n2026-11-03,Groceries,$412.35,Weekly groceries\n',
}

function useStatus() {
  const [status, setStatus] = useState<{ kind: 'ok' | 'error'; text: string } | null>(null)
  return {
    status,
    ok: (text: string) => setStatus({ kind: 'ok', text }),
    fail: (e: unknown, fallback: string) =>
      setStatus({ kind: 'error', text: e instanceof Error ? e.message : fallback }),
    clear: () => setStatus(null),
  }
}

function Status({ status }: { status: ReturnType<typeof useStatus>['status'] }) {
  if (!status) return null
  return (
    <p className={status.kind === 'ok' ? 'field-ok' : 'field-error'} role={status.kind === 'ok' ? 'status' : 'alert'}>
      {status.text}
    </p>
  )
}

function DataSection() {
  const { data, api, mutate, setup } = useReadyWorkspace()
  const [rowErrors, setRowErrors] = useState<RowError[]>([])
  const [switchTo, setSwitchTo] = useState<Market | null>(null)
  const [busy, setBusy] = useState(false)
  const file = useRef<HTMLInputElement>(null)
  const s = useStatus()
  const samples = sampleParts(data)

  async function upload(f: File) {
    setBusy(true)
    s.clear()
    setRowErrors([])
    try {
      await mutate(() => api.upload(f))
      s.ok(`${f.name} is now your statement. Every page uses it.`)
    } catch (e) {
      if (e instanceof ApiError) setRowErrors(e.rowErrors)
      s.fail(e, 'That file couldn’t be read. Export it as CSV and try again.')
    } finally {
      setBusy(false)
    }
  }

  function downloadTemplate() {
    const url = URL.createObjectURL(new Blob([TEMPLATE[data.market]], { type: 'text/csv' }))
    const a = document.createElement('a')
    a.href = url
    a.download = `finbo-template-${data.market}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  async function confirmSwitch() {
    if (!switchTo) return
    setBusy(true)
    try {
      await setup(switchTo)
      s.ok(`Switched to ${switchTo === 'in' ? 'India' : 'the United States'} with fresh sample data.`)
    } catch (e) {
      s.fail(e, 'The switch didn’t go through. Try again.')
    } finally {
      setBusy(false)
      setSwitchTo(null)
    }
  }

  return (
    <section id="data" className="settings-section" aria-labelledby="data-title">
      <h2 id="data-title" className="section-title">
        Your statement
      </h2>
      {samples.length > 0 && (
        <Notice>
          <p>You’re using sample {samples.join(' and ')}. Replace them below.</p>
        </Notice>
      )}
      <p>
        Upload a CSV with <code>Date</code>, <code>Category</code> and <code>Amount</code> columns.
        Amounts can include {data.market === 'in' ? '₹, Rs. and lakh commas' : '$ and commas'}; dates
        can be YYYY-MM-DD or {data.market === 'in' ? 'DD/MM/YYYY' : 'MM/DD/YYYY'}.
      </p>
      <div className="row-actions">
        <button className="btn btn-primary" disabled={busy} onClick={() => file.current?.click()}>
          {busy ? 'Reading the file' : 'Upload a statement'}
        </button>
        <button className="link-button" onClick={downloadTemplate}>
          Download the CSV template
        </button>
        <input
          ref={file}
          type="file"
          accept=".csv,text/csv"
          hidden
          onChange={(e) => {
            const f = e.target.files?.[0]
            if (f) void upload(f)
            e.target.value = ''
          }}
        />
      </div>
      <Status status={s.status} />
      {rowErrors.length > 0 && (
        <ul className="row-errors">
          {rowErrors.map((r) => (
            <li key={`${r.line}-${r.column}`}>
              Line {r.line}, {r.column}: {r.message}
            </li>
          ))}
        </ul>
      )}

      <h3>Country</h3>
      <p>
        You’re set up for {data.market === 'in' ? 'India' : 'the United States'}. Switching country
        starts again from that country’s sample data.
      </p>
      <button
        className="btn btn-ghost"
        onClick={() => setSwitchTo(data.market === 'in' ? 'us' : 'in')}
      >
        Switch to {data.market === 'in' ? 'the United States' : 'India'}
      </button>
      <ConfirmDialog
        open={switchTo !== null}
        title="Switch country?"
        confirmLabel="Switch and reset"
        busy={busy}
        onConfirm={() => void confirmSwitch()}
        onClose={() => setSwitchTo(null)}
      >
        <p>
          Your statement, income, debts and decision log are replaced with sample data for{' '}
          {switchTo === 'us' ? 'the United States' : 'India'}. This can’t be undone.
        </p>
      </ConfirmDialog>
    </section>
  )
}

function ProfileSection() {
  const { data, api, mutate } = useReadyWorkspace()
  const p = data.profile
  const [income, setIncome] = useState(String(Number(p.monthly_income)))
  const [stability, setStability] = useState(p.income_stability)
  const [dependents, setDependents] = useState(String(p.dependents))
  const [fund, setFund] = useState(String(Number(p.emergency_fund_balance)))
  const [busy, setBusy] = useState(false)
  const s = useStatus()

  async function save(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    s.clear()
    try {
      await mutate(() =>
        api.updateProfile({
          monthly_income: income || '0',
          income_stability: stability,
          dependents: Number(dependents) || 0,
          emergency_fund_balance: fund || '0',
        }),
      )
      s.ok('Saved. Every page now uses these numbers.')
    } catch (err) {
      s.fail(err, 'Your details weren’t saved. Check the values and try again.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <section id="profile" className="settings-section" aria-labelledby="profile-title">
      <h2 id="profile-title" className="section-title">
        Income and safety net
      </h2>
      <form className="form-grid" onSubmit={save}>
        <label className="field">
          <span>Take-home income a month</span>
          <input type="number" min={0} step="any" required value={income} onChange={(e) => setIncome(e.target.value)} />
        </label>
        <label className="field">
          <span>Emergency fund today</span>
          <input type="number" min={0} step="any" required value={fund} onChange={(e) => setFund(e.target.value)} />
        </label>
        <label className="field">
          <span>People who depend on your income</span>
          <input type="number" min={0} max={20} step={1} required value={dependents} onChange={(e) => setDependents(e.target.value)} />
        </label>
        <fieldset className="field">
          <legend>Your income is</legend>
          <label className="radio">
            <input type="radio" name="stability" checked={stability === 'stable'} onChange={() => setStability('stable')} />
            About the same every month
          </label>
          <label className="radio">
            <input type="radio" name="stability" checked={stability === 'variable'} onChange={() => setStability('variable')} />
            Different month to month
          </label>
        </fieldset>
        <div className="form-actions">
          <button className="btn btn-primary" type="submit" disabled={busy}>
            {busy ? 'Saving' : 'Save income details'}
          </button>
          <Status status={s.status} />
        </div>
      </form>
    </section>
  )
}

type DebtRow = DebtInput & { key: number }

let rowKey = 0
const newRowKey = () => ++rowKey

function DebtsSection() {
  const { data, api, mutate } = useReadyWorkspace()
  const toRows = () =>
    data.profile.debts.map((d) => ({
      key: newRowKey(),
      name: d.name,
      balance: String(Number(d.balance)),
      annual_rate_pct: String(Number(d.annual_rate_pct)),
      minimum_payment: String(Number(d.minimum_payment)),
    }))
  const [rows, setRows] = useState<DebtRow[]>(toRows)
  const [busy, setBusy] = useState(false)
  const s = useStatus()

  function update(key: number, field: keyof DebtInput, value: string) {
    setRows((rs) => rs.map((r) => (r.key === key ? { ...r, [field]: value } : r)))
  }

  async function save(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    s.clear()
    try {
      await mutate(() => api.updateDebts(rows.map(({ key: _key, ...d }) => d)))
      s.ok(rows.length ? 'Saved. The debt plan is recalculated.' : 'Saved. You have no debts listed.')
    } catch (err) {
      s.fail(err, 'Your debts weren’t saved. Check each row and try again.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <section id="debts" className="settings-section" aria-labelledby="debts-title">
      <h2 id="debts-title" className="section-title">
        Debts
      </h2>
      <form onSubmit={save}>
        {rows.length === 0 && <p className="muted">No debts listed. Add one if you owe money on a card or loan.</p>}
        <div className="debt-rows">
          {rows.map((r, i) => (
            <fieldset key={r.key} className="debt-row">
              <legend className="visually-hidden">Debt {i + 1}</legend>
              <label className="field">
                <span>Name</span>
                <input required maxLength={60} value={r.name} onChange={(e) => update(r.key, 'name', e.target.value)} />
              </label>
              <label className="field">
                <span>Balance</span>
                <input type="number" min={0} step="any" required value={r.balance} onChange={(e) => update(r.key, 'balance', e.target.value)} />
              </label>
              <label className="field">
                <span>Rate a year (%)</span>
                <input type="number" min={0} max={100} step="any" required value={r.annual_rate_pct} onChange={(e) => update(r.key, 'annual_rate_pct', e.target.value)} />
              </label>
              <label className="field">
                <span>Minimum a month</span>
                <input type="number" min={0.01} step="any" required value={r.minimum_payment} onChange={(e) => update(r.key, 'minimum_payment', e.target.value)} />
              </label>
              <button
                type="button"
                className="link-button debt-remove"
                onClick={() => setRows((rs) => rs.filter((x) => x.key !== r.key))}
              >
                Remove {r.name || 'this debt'}
              </button>
            </fieldset>
          ))}
        </div>
        <div className="form-actions">
          <button
            type="button"
            className="btn btn-ghost"
            disabled={rows.length >= 20}
            onClick={() =>
              setRows((rs) => [
                ...rs,
                { key: newRowKey(), name: '', balance: '', annual_rate_pct: '', minimum_payment: '' },
              ])
            }
          >
            Add a debt
          </button>
          <button className="btn btn-primary" type="submit" disabled={busy}>
            {busy ? 'Saving' : 'Save debts'}
          </button>
          <Status status={s.status} />
        </div>
      </form>
    </section>
  )
}

function TelegramSection() {
  const { api } = useReadyWorkspace()
  const [status, setStatus] = useState<TelegramStatus | null>(null)
  const [code, setCode] = useState<TelegramCode | null>(null)
  const [busy, setBusy] = useState(false)
  const s = useStatus()

  useEffect(() => {
    api
      .telegram()
      .then(setStatus)
      .catch(() => setStatus(null))
  }, [api])

  async function getCode() {
    setBusy(true)
    s.clear()
    try {
      setCode(await api.telegramCode())
    } catch (e) {
      s.fail(e, 'The code wasn’t created. Try again.')
    } finally {
      setBusy(false)
    }
  }

  const configured = status?.bot.configured

  return (
    <section id="telegram" className="settings-section" aria-labelledby="telegram-title">
      <h2 id="telegram-title" className="section-title">
        Chat on Telegram
      </h2>
      <p>
        Talk to the whole crew from Telegram: send <code>/snowy when am I debt-free?</code>, tap
        quick questions, approve plans, and send your statement as a CSV.
      </p>
      {status?.linked && (
        <p className="field-ok" role="status">
          Your Telegram is connected. Chats, plans and numbers are shared.
        </p>
      )}
      {configured ? (
        <>
          {!status?.linked && (
            <p>Connect it once and Telegram will use the same numbers and plans as this app.</p>
          )}
          <div className="row-actions">
            <button className="btn btn-primary" disabled={busy} onClick={() => void getCode()}>
              {status?.linked ? 'Connect another Telegram account' : 'Connect Telegram'}
            </button>
            {status?.bot.url && (
              <a className="btn btn-soft" href={status.bot.url} target="_blank" rel="noopener noreferrer">
                Open the bot
              </a>
            )}
          </div>
          {code && (
            <div className="code-box" role="status">
              <p>
                Send this to the bot within 10 minutes: <code className="code">/link {code.code}</code>
              </p>
              {code.deep_link && (
                <a className="btn btn-accent" href={code.deep_link} target="_blank" rel="noopener noreferrer">
                  Open Telegram and connect
                </a>
              )}
            </div>
          )}
        </>
      ) : (
        <p className="muted">
          {status === null
            ? 'Checking whether the Telegram bot is available.'
            : 'The Telegram bot isn’t running on this server yet. It needs a free bot token from @BotFather (TELEGRAM_BOT_TOKEN and TELEGRAM_BOT_USERNAME); docs/DEPLOY.md has the steps.'}
        </p>
      )}
      <Status status={s.status} />
    </section>
  )
}

function SheetsSection() {
  const { api, reload } = useReadyWorkspace()
  const [busy, setBusy] = useState<string | null>(null)
  const [msConfigured, setMsConfigured] = useState<boolean | null>(null)
  const [webUrl, setWebUrl] = useState<string | null>(null)
  const file = useRef<HTMLInputElement>(null)
  const s = useStatus()

  useEffect(() => {
    publicApi
      .health()
      .then((h) => setMsConfigured(h.microsoft && Boolean(MS_CLIENT_ID)))
      .catch(() => setMsConfigured(false))
  }, [])

  function recordedText(n: number, where: string) {
    return n === 0
      ? `No new decisions found in ${where}. Mark a plan Approved or Sent back in the Approvals sheet first.`
      : `Recorded ${n} decision${n === 1 ? '' : 's'} from ${where}. See them in Decisions.`
  }

  async function run(label: string, action: () => Promise<void>) {
    setBusy(label)
    s.clear()
    try {
      await action()
    } catch (e) {
      s.fail(e, 'That didn’t work. Try again.')
    } finally {
      setBusy(null)
    }
  }

  const download = () =>
    run('download', async () => {
      const blob = await api.exportXlsx()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `finbo-plan-${new Date().toISOString().slice(0, 10)}.xlsx`
      a.click()
      URL.revokeObjectURL(url)
      s.ok('Downloaded. Open the Approvals sheet to approve or send back each plan.')
    })

  const upload = (f: File) =>
    run('import', async () => {
      const { recorded } = await api.importXlsx(f)
      reload()
      s.ok(recordedText(recorded.length, f.name))
    })

  const push = () =>
    run('push', async () => {
      const res = await api.onedrivePush(await graphToken())
      setWebUrl(res.web_url)
      s.ok(`Saved to your OneDrive as ${res.path}.`)
    })

  const pull = () =>
    run('pull', async () => {
      const { recorded } = await api.onedrivePull(await graphToken())
      reload()
      s.ok(recordedText(recorded.length, 'OneDrive'))
    })

  return (
    <section id="excel" className="settings-section" aria-labelledby="excel-title">
      <h2 id="excel-title" className="section-title">
        Excel and OneDrive
      </h2>
      <p>
        Download your plan as an Excel workbook. Its Approvals sheet lists each plan Finbo
        proposes; set Status to Approved or Sent back, save, and import the file here. Only plans
        Finbo proposed can be approved this way.
      </p>
      <div className="row-actions">
        <button className="btn btn-primary" disabled={busy !== null} onClick={() => void download()}>
          {busy === 'download' ? 'Preparing the workbook' : 'Download as Excel'}
        </button>
        <button className="btn btn-ghost" disabled={busy !== null} onClick={() => file.current?.click()}>
          {busy === 'import' ? 'Reading the workbook' : 'Import a marked-up workbook'}
        </button>
        <input
          ref={file}
          type="file"
          accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
          hidden
          onChange={(e) => {
            const f = e.target.files?.[0]
            if (f) void upload(f)
            e.target.value = ''
          }}
        />
      </div>

      <h3>OneDrive or SharePoint</h3>
      {msConfigured ? (
        <>
          <p>
            Keep the workbook in your OneDrive and edit it there, then read your decisions back.
            You’ll sign in to Microsoft in a popup the first time.
          </p>
          <div className="row-actions">
            <button className="btn btn-ghost" disabled={busy !== null} onClick={() => void push()}>
              {busy === 'push' ? 'Saving to OneDrive' : 'Save to OneDrive'}
            </button>
            <button className="btn btn-ghost" disabled={busy !== null} onClick={() => void pull()}>
              {busy === 'pull' ? 'Reading from OneDrive' : 'Read decisions from OneDrive'}
            </button>
          </div>
          {webUrl && (
            <p>
              <a href={webUrl} target="_blank" rel="noopener noreferrer">
                Open the workbook in OneDrive
              </a>
            </p>
          )}
        </>
      ) : (
        <p className="muted">
          {msConfigured === null
            ? 'Checking whether OneDrive sync is available.'
            : 'OneDrive sync isn’t set up on this server. It needs a free Microsoft app registration (MS_CLIENT_ID); docs/DEPLOY.md has the steps. Excel download and import above work without it.'}
        </p>
      )}
      <Status status={s.status} />
    </section>
  )
}

function DangerSection() {
  const { api, reload } = useReadyWorkspace()
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const s = useStatus()

  async function remove() {
    setBusy(true)
    try {
      await api.deleteData()
      setOpen(false)
      reload()
    } catch (e) {
      s.fail(e, 'Your data wasn’t deleted. Try again.')
      setBusy(false)
    }
  }

  return (
    <section id="account" className="settings-section" aria-labelledby="account-title">
      <h2 id="account-title" className="section-title">
        Appearance and account
      </h2>
      <div className="row-actions">
        <ThemeToggle className="btn btn-ghost" />
      </div>
      <p>
        Deleting your data removes your statement, income, debts, decisions and activity log from
        Finbo’s database.
        Your sign-in account stays; manage it from the account button at the top of the page.
      </p>
      <button className="btn btn-danger" onClick={() => setOpen(true)}>
        Delete my Finbo data
      </button>
      <Status status={s.status} />
      <ConfirmDialog
        open={open}
        title="Delete your data?"
        confirmLabel="Delete my data"
        busy={busy}
        onConfirm={() => void remove()}
        onClose={() => setOpen(false)}
      >
        <p>
          Your statement, income, debts, decisions and activity log are removed. This can’t be
          undone.
        </p>
      </ConfirmDialog>
    </section>
  )
}

export function Settings() {
  const { hash } = useLocation()
  const { data } = useReadyWorkspace()

  useEffect(() => {
    if (hash) document.getElementById(hash.slice(1))?.scrollIntoView()
  }, [hash])

  return (
    <div className="page page-settings">
      <header className="page-intro">
        <h1 className="page-title">Settings</h1>
        <p className="page-sub">
          Your statement, your numbers, Telegram and your account. Changes apply everywhere
          straight away.
        </p>
      </header>
      <nav className="settings-index" aria-label="Settings sections">
        <a href="#data">Statement</a>
        <a href="#profile">Income</a>
        <a href="#debts">Debts</a>
        <a href="#telegram">Telegram</a>
        <a href="#excel">Excel</a>
        <a href="#account">Account</a>
      </nav>
      <div className="settings-sections">
        {/* Reset the forms only when a country switch replaces the data. Keying on the
            data itself would remount on every save and wipe the "Saved" message. */}
        <DataSection />
        <ProfileSection key={`p-${data.market}`} />
        <DebtsSection key={`d-${data.market}`} />
        <TelegramSection />
        <SheetsSection />
        <DangerSection />
      </div>
    </div>
  )
}
