import { ArrowRight } from 'lucide-react'
import { Link } from 'react-router'

import { Button } from '@/components/ui/button'
import { Reveal } from '@/features/landing/Reveal'

/** Final call to action and footer. */
export function Closing({ appHref, appLabel }: { appHref: string; appLabel: string }) {
  return (
    <>
      <section className="mx-auto max-w-6xl px-6 py-24">
        <Reveal>
          <div className="relative overflow-hidden rounded-3xl bg-linear-to-br from-brand-deep via-primary to-brand-ink px-8 py-16 text-center text-white sm:px-16">
            <div
              aria-hidden="true"
              className="absolute -top-24 -right-24 size-72 rounded-full bg-brand-glow/30 blur-3xl"
            />
            <div
              aria-hidden="true"
              className="absolute -bottom-24 -left-24 size-72 rounded-full bg-status-full/20 blur-3xl"
            />
            <h2 className="relative mx-auto max-w-2xl text-3xl font-semibold tracking-tight text-balance sm:text-4xl">
              Spend your time winning tenders, not formatting them.
            </h2>
            <p className="relative mx-auto mt-4 max-w-xl text-white/75">
              Upload your next RFP and see the compliance matrix fill itself in.
            </p>
            <Button
              asChild
              size="lg"
              className="relative mt-8 h-11 bg-white px-6 text-brand-ink hover:bg-white/90"
            >
              <Link to={appHref}>
                {appLabel}
                <ArrowRight aria-hidden="true" />
              </Link>
            </Button>
          </div>
        </Reveal>
      </section>
      <footer className="border-t border-border">
        <div className="mx-auto flex max-w-6xl flex-col gap-3 px-6 py-8 text-sm text-muted-foreground sm:flex-row sm:items-center sm:justify-between">
          <span className="flex items-center gap-2 font-medium text-foreground">
            <span aria-hidden="true" className="size-5 rounded-md bg-primary" />
            BidReady
          </span>
          <span>RFP compliance matrix and auto-drafter · Automate Your Boring Task</span>
        </div>
      </footer>
    </>
  )
}
