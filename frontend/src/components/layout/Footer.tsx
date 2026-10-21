import { Link } from 'react-router-dom'
import { Container, Logo } from '@/components/ui'

export function Footer() {
  const year = new Date().getFullYear()
  return (
    <footer className="on-dark mt-auto bg-navy text-on-navy-muted">
      <Container className="py-10">
        <div className="grid gap-8 md:grid-cols-[1.4fr_1fr_1fr]">
          <div className="max-w-sm">
            <Logo onDark />
            <p className="type-body mt-3">
              An AI assistant that answers questions about your own PayPal payment data, using retrieved records and
              deterministic calculations.
            </p>
          </div>
          <nav aria-label="Product">
            <h2 className="type-label text-white">Product</h2>
            <ul className="type-body mt-3 space-y-2">
              <li>
                <Link className="hover:text-white" to="/#how-it-works">
                  How it works
                </Link>
              </li>
              <li>
                <Link className="hover:text-white" to="/#capabilities">
                  Capabilities
                </Link>
              </li>
              <li>
                <Link className="hover:text-white" to="/#roadmap">
                  Roadmap
                </Link>
              </li>
            </ul>
          </nav>
          <nav aria-label="Legal and support">
            <h2 className="type-label text-white">Legal &amp; support</h2>
            <ul className="type-body mt-3 space-y-2">
              <li>
                <Link className="hover:text-white" to="/privacy">
                  Privacy (draft)
                </Link>
              </li>
              <li>
                <Link className="hover:text-white" to="/terms">
                  Terms (draft)
                </Link>
              </li>
              <li>
                <span className="opacity-80">Help &amp; contact — not available in this prototype</span>
              </li>
            </ul>
          </nav>
        </div>
        <div className="mt-8 flex flex-col gap-2 border-t border-on-navy-line pt-6 text-sm">
          <p>
            PayPilot is an independent product. It is not affiliated with, endorsed by, or sponsored by PayPal. PayPal is
            a trademark of its respective owner.
          </p>
          <p>© {year} PayPilot contributors. Open-source prototype built for demonstration; not financial advice.</p>
        </div>
      </Container>
    </footer>
  )
}
