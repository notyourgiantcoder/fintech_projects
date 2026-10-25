// Typed client for the Finbo API. Money values arrive as decimal strings.

export type Market = 'in' | 'us'
export type Currency = 'INR' | 'USD'
export type Bucket = 'needs' | 'wants' | 'savings' | 'unclassified'
export type FiledBucket = Exclude<Bucket, 'unclassified'>
export type Strategy = 'avalanche' | 'snowball'

export interface Debt {
  name: string
  balance: string
  annual_rate_pct: string
  minimum_payment: string
  currency: Currency
}

export interface Profile {
  currency: Currency
  monthly_income: string
  income_stability: 'stable' | 'variable'
  dependents: number
  emergency_fund_balance: string
  debts: Debt[]
}

export interface CategoryShare {
  category: string
  bucket: Bucket
  total: string
  monthly_avg: string
  share_pct: string
}

export interface BucketShare {
  bucket: Bucket
  monthly_avg: string
  pct_of_income: string | null
  target_pct: string | null
}

export interface Spending {
  currency: Currency
  period_start: string
  period_end: string
  months: number
  monthly_income: string
  total_outflow: string
  avg_monthly_spending: string
  avg_monthly_savings: string
  savings_rate_pct: string | null
  categories: CategoryShare[]
  buckets: BucketShare[]
  monthly_totals: { month: string; total: string }[]
  unclassified_categories: string[]
}

export interface EmergencyFund {
  plan: {
    target_months: number
    monthly_essential_expenses: string
    target_amount: string
    current_balance: string
    gap: string
    coverage_months: string | null
    monthly_contribution: string
    months_to_target: number | null
    is_funded: boolean
  }
  assumptions: string[]
}

export interface PayoffPlan {
  strategy: Strategy
  monthly_budget: string
  months: number
  first_payoff_month: number
  total_interest: string
  total_paid: string
  target_order: string[]
  payoff_order: { name: string; month_paid_off: number; interest_paid: string }[]
}

export interface DebtComparison {
  monthly_budget: string
  sum_of_minimums: string
  comparison: {
    avalanche: PayoffPlan
    snowball: PayoffPlan
    interest_saved_with_avalanche: string
    months_saved_with_avalanche: number
    earlier_first_win_with_snowball: number
    cheapest: Strategy
  }
  assumptions: string[]
}

export type DebtResult = DebtComparison | { message: string } | { error: string }

export interface Approval {
  id: string
  subject: string
  decision: 'approved' | 'sent_back'
  note: string
  source: 'app' | 'excel'
  decided_at: string
}

export interface Calculations {
  market: Market
  currency: Currency
  profile: Profile
  spending: Spending
  emergency_fund: EmergencyFund
  debt: DebtResult
  extra_debt_payment: number
  overrides: Record<string, FiledBucket>
}

export interface Workspace extends Calculations {
  sources: { transactions: 'sample' | 'uploaded'; profile: 'sample' | 'edited' }
  watchlist: string[]
  approvals: Approval[]
}

export interface Checks {
  refused: string | null
  pii_redacted: Record<string, number>
  input_flags: string[]
  figures_checked: number
  unverified_figures: string[]
  risky_phrases: string[]
  sources_withheld: number
  disclaimer_added: boolean
}

export interface Quote {
  symbol: string
  name: string | null
  exchange: string | null
  currency: string
  price: string
  previous_close: string | null
  change_pct: string | null
  day_low: string | null
  day_high: string | null
  year_low: string | null
  year_high: string | null
  market_cap: string | null
  as_of: string
}

export interface WatchRow {
  symbol: string
  quote?: Quote
  error?: string
}

export interface SymbolMatch {
  symbol: string
  name: string | null
  exchange: string | null
  kind: string | null
}

export interface SymbolDetail {
  symbol: string
  quote: Quote
  stats?: {
    start: string
    end: string
    return_pct: string
    annualised_volatility_pct: string | null
    max_drawdown_pct: string
    high: string
    low: string
  }
  profile?: {
    name: string | null
    sector: string | null
    industry: string | null
    trailing_pe: string | null
    dividend_yield_pct: string | null
    summary: string | null
  }
  news?: { title: string; source: string | null; link: string; published: string | null }[]
  filings?: { form: string; filed: string; description: string | null; url: string }[]
  errors: Record<string, string>
}

export interface ActivityEvent {
  id: number
  created_at: string
  kind: 'setup' | 'ask' | 'refused' | 'upload' | 'excel_import' | 'onedrive_push' | string
  summary: string
  payload: { checks?: Checks; provider?: string | null; model?: string | null }
}

export interface TraceCall {
  name: string
  arguments: Record<string, unknown>
  depth: number
  ok: boolean | null
}

export interface Answer {
  answer: string
  provider: string | null
  model: string | null
  fallbacks: string[]
  trace: TraceCall[]
  checks: Checks
}

export interface RowError {
  line: number
  column: string
  value: string
  message: string
}

export interface Health {
  auth: 'clerk' | 'dev' | 'unconfigured'
  providers: { name: string; configured: boolean }[]
  microsoft: boolean
  telegram: { configured: boolean; url: string | null }
}

export interface ProfileInput {
  monthly_income: string
  income_stability: 'stable' | 'variable'
  dependents: number
  emergency_fund_balance: string
}

export type DebtInput = Omit<Debt, 'currency'>

// ---------- Crew and chat ----------

export type CrewId = 'finbo' | 'penny' | 'hazel' | 'snowy' | 'bruno' | 'scout'

export interface QuickAction {
  id: string
  label: string
  needs: 'symbol' | 'topic' | null
}

export interface CrewMember {
  id: CrewId
  name: string
  animal: string
  emoji: string
  color: string
  role: string
  helps_with: string
  greeting: string
  quick_actions: QuickAction[]
}

export interface CardAction {
  kind: 'approve' | 'send_back' | 'file' | 'quick' | 'watch'
  label: string
  payload: Record<string, unknown>
}

export interface ChatCard {
  kind: string
  title: string
  // Shape depends on kind; values arrive pre-formatted by the server (same as Telegram).
  data: Record<string, any> // eslint-disable-line @typescript-eslint/no-explicit-any
  actions: CardAction[]
  outcome?: string
}

export interface ChatMessage {
  id: number
  thread: CrewId
  role: 'user' | 'agent'
  author: CrewId | 'you'
  text: string
  cards: ChatCard[]
  meta: {
    mode?: 'quick' | 'ai' | 'offline' | 'action' | 'error'
    note?: string
    contributors?: CrewId[]
    checks?: Checks
    provider?: string | null
  }
  channel: string
  created_at: string
}

export interface DemoReply {
  author: CrewId
  text: string
  cards: ChatCard[]
}

export interface TelegramStatus {
  linked: boolean
  bot: { configured: boolean; username: string | null; url: string | null }
}

export interface TelegramCode {
  code: string
  expires_at: string
  deep_link: string | null
  bot: TelegramStatus['bot']
}

export function hasComparison(debt: DebtResult): debt is DebtComparison {
  return 'comparison' in debt
}

export class ApiError extends Error {
  status: number
  rowErrors: RowError[]

  constructor(status: number, message: string, rowErrors: RowError[] = []) {
    super(message)
    this.status = status
    this.rowErrors = rowErrors
  }
}

type GetToken = () => Promise<string | null>

async function request<T>(getToken: GetToken | null, path: string, init: RequestInit = {}) {
  const headers = new Headers(init.headers)
  const token = getToken ? await getToken() : null
  if (token) headers.set('Authorization', `Bearer ${token}`)
  let res: Response
  try {
    res = await fetch(`/api${path}`, { ...init, headers })
  } catch {
    throw new ApiError(0, 'The Finbo server isn’t reachable. Start it with `finbo serve`.')
  }
  if (res.status === 204) return undefined as T
  const body = await res.json().catch(() => ({}))
  if (!res.ok) {
    const detail = typeof body.detail === 'string' ? body.detail : `Request failed (${res.status})`
    throw new ApiError(res.status, detail, body.errors ?? [])
  }
  return body as T
}

const json = (method: string, body: unknown): RequestInit => ({
  method,
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
})

export const publicApi = {
  health: () => request<Health>(null, '/health'),
  crew: () => request<CrewMember[]>(null, '/crew'),
  demoQuick: (agent: CrewId, action: string, market: Market, arg?: string) =>
    request<DemoReply>(
      null,
      `/demo/quick/${agent}/${action}?${new URLSearchParams({ market, ...(arg ? { arg } : {}) })}`,
    ),
  demo: (market: Market, extra: number) =>
    request<Calculations>(null, `/demo?market=${market}&extra_debt_payment=${extra}`),
}

export function createApi(getToken: GetToken) {
  const call = <T>(path: string, init?: RequestInit) => request<T>(getToken, path, init)
  return {
    me: (extra: number, contribution: number | null) => {
      const params = new URLSearchParams({ extra_debt_payment: String(extra) })
      if (contribution != null) params.set('ef_contribution', String(contribution))
      return call<Workspace>(`/me?${params}`)
    },
    setup: (market: Market) => call<Workspace>('/me/setup', json('POST', { market })),
    deleteData: () => call<void>('/me', { method: 'DELETE' }),
    updateProfile: (body: ProfileInput) => call<Workspace>('/me/profile', json('PUT', body)),
    updateDebts: (body: DebtInput[]) => call<Workspace>('/me/debts', json('PUT', body)),
    classify: (category: string, bucket: FiledBucket) =>
      call<Workspace>('/me/classify', json('POST', { category, bucket })),
    upload: (file: File) => {
      const form = new FormData()
      form.append('file', file)
      return call<Workspace>('/me/transactions', { method: 'POST', body: form })
    },
    ask: (question: string) => call<Answer>('/me/ask', json('POST', { question })),
    decide: (subject: string, decision: Approval['decision']) =>
      call<Approval>('/me/approvals', json('POST', { subject, decision })),
    activity: () => call<ActivityEvent[]>('/me/activity'),
    chats: () => call<Partial<Record<CrewId, ChatMessage>>>('/me/chats'),
    chat: (thread: CrewId) => call<ChatMessage[]>(`/me/chat/${thread}`),
    send: (thread: CrewId, text: string) =>
      call<ChatMessage[]>(`/me/chat/${thread}`, json('POST', { text })),
    quick: (thread: CrewId, action: string, arg?: string) =>
      call<ChatMessage[]>(`/me/chat/${thread}/quick`, json('POST', { action, arg })),
    act: (message_id: number, card: number, action: number) =>
      call<ChatMessage[]>('/me/chat-action', json('POST', { message_id, card, action })),
    clearChat: (thread: CrewId) => call<void>(`/me/chat/${thread}`, { method: 'DELETE' }),
    telegram: () => call<TelegramStatus>('/me/telegram'),
    telegramCode: () => call<TelegramCode>('/me/telegram/code', { method: 'POST' }),
    watchlist: () => call<WatchRow[]>('/me/watchlist'),
    setWatchlist: (symbols: string[]) =>
      call<string[]>('/me/watchlist', json('PUT', { symbols })),
    searchSymbols: (q: string) =>
      call<SymbolMatch[]>(`/market/search?${new URLSearchParams({ q })}`),
    symbol: (symbol: string) =>
      call<SymbolDetail>(`/market/symbol/${encodeURIComponent(symbol)}`),
    exportXlsx: async () => {
      const token = await getToken()
      const res = await fetch('/api/me/export.xlsx', {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      }).catch(() => null)
      if (!res || !res.ok) throw new ApiError(res?.status ?? 0, 'The workbook couldn’t be created.')
      return res.blob()
    },
    importXlsx: (file: File) => {
      const form = new FormData()
      form.append('file', file)
      return call<{ recorded: Approval[] }>('/me/import.xlsx', { method: 'POST', body: form })
    },
    onedrivePush: (graphToken: string) =>
      call<{ web_url: string; path: string }>('/me/onedrive/push', {
        method: 'POST',
        headers: { 'X-Graph-Token': graphToken },
      }),
    onedrivePull: (graphToken: string) =>
      call<{ recorded: Approval[] }>('/me/onedrive/pull', {
        method: 'POST',
        headers: { 'X-Graph-Token': graphToken },
      }),
  }
}

export type Api = ReturnType<typeof createApi>
