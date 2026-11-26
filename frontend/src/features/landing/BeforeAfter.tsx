import { CheckCircle2, Clock, XCircle, Zap } from 'lucide-react'

import { Reveal } from '@/features/landing/Reveal'

const BEFORE = [
  'Highlight 100+ pages and copy every "shall" into Excel',
  'Hunt through old proposals and copy-paste answers',
  'Re-type company details into every annexure',
  'Re-read the corrigendum to find what changed',
  'Hope nobody missed a mandatory clause',
]
const AFTER = [
  'Every requirement, rule and scoring criterion extracted',
  'Answers drafted from your documents, each with a source',
  'Forms filled from your profile, gaps highlighted',
  'Addenda diffed word by word, only changed rows re-drafted',
  'A readiness score that blocks what would get you rejected',
]

export function BeforeAfter() {
  return (
    <section className="mx-auto max-w-6xl px-6 py-24">
      <Reveal className="mx-auto max-w-2xl text-center">
        <p className="text-sm font-medium text-primary">The boring part, automated</p>
        <h2 className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">
          From a week of copy-paste to a coffee break
        </h2>
        <p className="mt-4 text-muted-foreground">
          A tender response is mostly reading, copying and formatting. BidReady does that work so
          your team can spend its time on strategy and price.
        </p>
      </Reveal>
      <div className="mt-14 grid gap-6 md:grid-cols-2">
        <Reveal>
          <div className="h-full rounded-2xl border border-border bg-muted/40 p-7">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold">Today</h3>
              <span className="inline-flex items-center gap-1.5 rounded-full bg-status-gap/10 px-3 py-1 text-xs font-medium text-status-gap">
                <Clock aria-hidden="true" className="size-3.5" /> 3 to 5 days
              </span>
            </div>
            <ul className="mt-6 flex flex-col gap-3">
              {BEFORE.map((item) => (
                <li key={item} className="flex gap-3 text-sm text-muted-foreground">
                  <XCircle aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-status-gap" />
                  {item}
                </li>
              ))}
            </ul>
          </div>
        </Reveal>
        <Reveal delay={120}>
          <div className="relative h-full overflow-hidden rounded-2xl border border-primary/30 bg-linear-to-br from-primary/10 via-background to-background p-7 shadow-[0_20px_60px_-30px_var(--primary)]">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold">With BidReady</h3>
              <span className="inline-flex items-center gap-1.5 rounded-full bg-status-full/10 px-3 py-1 text-xs font-medium text-status-full">
                <Zap aria-hidden="true" className="size-3.5" /> minutes + your review
              </span>
            </div>
            <ul className="mt-6 flex flex-col gap-3">
              {AFTER.map((item) => (
                <li key={item} className="flex gap-3 text-sm">
                  <CheckCircle2
                    aria-hidden="true"
                    className="mt-0.5 size-4 shrink-0 text-status-full"
                  />
                  {item}
                </li>
              ))}
            </ul>
          </div>
        </Reveal>
      </div>
    </section>
  )
}
