import { Link } from 'react-router-dom'
import {
  ArrowRight,
  Database,
  FileSearch,
  Globe2,
  Lock,
  MessageSquareText,
  PlugZap,
  Scale,
  ShieldCheck,
  type LucideIcon,
} from 'lucide-react'
import { Badge, Container, buttonStyles } from '@/components/ui'

const steps: { icon: LucideIcon; title: string; body: string }[] = [
  {
    icon: PlugZap,
    title: 'Connect PayPal (sandbox)',
    body: 'PayPilot verifies your PayPal REST credentials on the server. Nothing is shown as connected until a real API call succeeds.',
  },
  {
    icon: Database,
    title: 'Sync your records',
    body: 'Transactions and invoices are imported into your private workspace, keeping PayPal’s own identifiers and statuses.',
  },
  {
    icon: MessageSquareText,
    title: 'Ask in plain English',
    body: 'The assistant chooses read-only tools, the backend runs them, and the answer cites the records it used.',
  },
]

const capabilities: { icon: LucideIcon; title: string; body: string }[] = [
  {
    icon: FileSearch,
    title: 'Evidence-grounded answers',
    body: 'Every answer points to retrieved records or a computed summary, with date range, currency and status. Missing data is stated, not guessed.',
  },
  {
    icon: Scale,
    title: 'Deterministic money maths',
    body: 'Totals come from decimal arithmetic in backend code. The AI explains results; it never produces the numbers.',
  },
  {
    icon: Globe2,
    title: 'Currency and status aware',
    body: 'Currencies are never mixed into one total. Pending is not completed, and an unpaid invoice is not money received.',
  },
  {
    icon: ShieldCheck,
    title: 'Read-only by design',
    body: 'The assistant cannot send reminders, create invoices, move money or issue refunds. It can only recommend.',
  },
  {
    icon: Lock,
    title: 'Merchant isolation',
    body: 'Every record, conversation and tool call is scoped to the signed-in merchant on the server, not in the browser.',
  },
]

const roadmap = [
  'Revenue recovery prioritisation',
  'Approved payment reminders',
  'Invoice creation and sending',
  'Payment-to-order reconciliation',
  'Exception management',
  'Refund workflows with approvals',
  'Audit and impact dashboards',
]

function IllustrativeConversation() {
  return (
    <figure className="rounded-lg border border-on-navy-line bg-navy p-4 shadow-pop sm:p-5" aria-label="Illustration of the assistant">
      <figcaption className="mb-3 flex flex-wrap items-center gap-2">
        <Badge tone="teal">Illustration</Badge>
        <span className="text-xs text-on-navy-muted">Sample wording only — not real account data.</span>
      </figcaption>
      <div className="space-y-3 text-sm">
        <div className="ml-auto max-w-[85%] rounded-lg bg-brand px-3.5 py-2.5 text-white">Which payments are pending?</div>
        <div className="max-w-[92%] space-y-2 rounded-lg border border-on-navy-line bg-navy-deep px-3.5 py-3 text-white">
          <p className="text-xs font-semibold tracking-wide text-teal uppercase">From your synced records</p>
          <p>The assistant lists pending transactions it retrieved, with each record’s ID, amount, currency and date.</p>
          <p className="text-xs font-semibold tracking-wide text-teal uppercase">Explanation</p>
          <p className="text-on-navy-muted">
            Pending items have not completed and are not counted as money received. It will say so, and suggest what to
            review next.
          </p>
        </div>
      </div>
    </figure>
  )
}

export function LandingPage() {
  return (
    <>
      <section className="on-dark bg-navy text-white">
        <Container className="grid items-center gap-10 py-14 sm:py-20 lg:grid-cols-[1.1fr_0.9fr] lg:gap-14">
          <div>
            <Badge tone="teal">Hackathon prototype · PayPal sandbox</Badge>
            <h1 className="type-display mt-5">Your AI revenue recovery agent.</h1>
            <p className="mt-5 max-w-xl text-lg text-on-navy-muted">
              PayPilot uses PayPal to help small businesses understand their payments, spot unpaid invoices and see what
              needs attention — with every figure computed from your real records.
            </p>
            <div className="mt-8 flex flex-col gap-3 sm:flex-row">
              <Link to="/register" className={buttonStyles({ variant: 'onDark', size: 'lg' })}>
                Create a merchant account <ArrowRight className="size-5" aria-hidden />
              </Link>
              <Link
                to="/login"
                className={buttonStyles({ variant: 'ghost', size: 'lg', className: 'border border-on-navy-line text-white hover:bg-white/10' })}
              >
                Sign in
              </Link>
            </div>
            <p className="mt-4 text-sm text-on-navy-muted">
              Runs against the PayPal sandbox only. No real money is moved.
            </p>
          </div>
          <IllustrativeConversation />
        </Container>
      </section>

      <section id="how-it-works" className="scroll-mt-20 py-14 sm:py-20">
        <Container>
          <h2 className="type-section">How it works</h2>
          <p className="type-body mt-2 max-w-2xl text-muted">Three steps from credentials to grounded answers.</p>
          <ol className="mt-8 grid gap-4 md:grid-cols-3">
            {steps.map((step, i) => (
              <li key={step.title} className="rounded-lg border border-line bg-surface p-5 shadow-card">
                <div className="flex items-center gap-3">
                  <span className="grid size-10 place-items-center rounded-md bg-teal-soft text-navy">
                    <step.icon className="size-5" aria-hidden />
                  </span>
                  <span className="type-label text-muted">Step {i + 1}</span>
                </div>
                <h3 className="type-card-title mt-4">{step.title}</h3>
                <p className="type-body mt-1.5 text-muted">{step.body}</p>
              </li>
            ))}
          </ol>
        </Container>
      </section>

      <section id="capabilities" className="scroll-mt-20 border-y border-line bg-surface py-14 sm:py-20">
        <Container>
          <h2 className="type-section">Built to be trusted with money questions</h2>
          <p className="type-body mt-2 max-w-2xl text-muted">
            A finance assistant is only useful if it is honest. These constraints are enforced in backend code, not in a
            prompt.
          </p>
          <ul className="mt-8 grid gap-x-8 gap-y-6 sm:grid-cols-2 lg:grid-cols-3">
            {capabilities.map((c) => (
              <li key={c.title} className="flex gap-4">
                <span className="grid size-10 shrink-0 place-items-center rounded-md bg-navy text-teal">
                  <c.icon className="size-5" aria-hidden />
                </span>
                <div>
                  <h3 className="type-card-title">{c.title}</h3>
                  <p className="type-body mt-1 text-muted">{c.body}</p>
                </div>
              </li>
            ))}
          </ul>
        </Container>
      </section>

      <section id="roadmap" className="scroll-mt-20 py-14 sm:py-20">
        <Container>
          <h2 className="type-section">Roadmap</h2>
          <p className="type-body mt-2 max-w-2xl text-muted">
            These are planned, <strong className="text-ink">not available today</strong>. The current build is read-only.
          </p>
          <ul className="mt-6 flex flex-wrap gap-2">
            {roadmap.map((item) => (
              <li key={item}>
                <Badge tone="neutral" dot={false}>
                  {item} · planned
                </Badge>
              </li>
            ))}
          </ul>
        </Container>
      </section>

      <section className="on-dark bg-navy-deep py-12 text-white">
        <Container className="flex flex-col items-start justify-between gap-5 sm:flex-row sm:items-center">
          <div>
            <h2 className="type-section">See your own payments, explained.</h2>
            <p className="mt-1 text-on-navy-muted">Create an account and connect your PayPal sandbox app.</p>
          </div>
          <Link to="/register" className={buttonStyles({ variant: 'onDark', size: 'lg' })}>
            Get started
          </Link>
        </Container>
      </section>
    </>
  )
}
