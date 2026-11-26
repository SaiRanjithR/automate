import {
  Gauge,
  GitCompare,
  Package,
  Quote,
  ScanSearch,
  ShieldCheck,
  Trophy,
  WifiOff,
  type LucideIcon,
} from 'lucide-react'

import { Reveal } from '@/features/landing/Reveal'

const FEATURES: { icon: LucideIcon; title: string; text: string }[] = [
  {
    icon: ScanSearch,
    title: 'Every requirement found',
    text: 'Clauses, tables, bullet lists and annexures — disclaimers and the buyer’s own duties left out.',
  },
  {
    icon: Quote,
    title: 'Answers with sources',
    text: 'Each answer quotes the file and page it came from. No evidence means a visible gap, never an invented claim.',
  },
  {
    icon: ShieldCheck,
    title: 'Live compliance review',
    text: 'Missing parts, unsupported claims and vague wording are flagged the moment an answer is drafted.',
  },
  {
    icon: Gauge,
    title: 'Go / no-go in seconds',
    text: 'Fit, eligibility, time left and competition rolled into one decision with reasons.',
  },
  {
    icon: GitCompare,
    title: 'Addenda handled',
    text: 'Changed, new and deleted clauses detected; only the affected answers are re-drafted.',
  },
  {
    icon: Package,
    title: 'Ready-to-sign package',
    text: 'Files formatted and named exactly as the tender demands, zipped for upload.',
  },
  {
    icon: Trophy,
    title: 'Learns from your wins',
    text: 'Evidence from won bids ranks higher; approved answers are reused in the next tender.',
  },
  {
    icon: WifiOff,
    title: 'Private by default',
    text: 'Runs on your machine. An offline mode makes no external calls at all.',
  },
]

export function Features() {
  return (
    <section id="features" className="mx-auto max-w-6xl scroll-mt-20 px-6 py-24">
      <Reveal className="max-w-2xl">
        <p className="text-sm font-medium text-primary">What it does</p>
        <h2 className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">
          Your bid team’s sharpest assistant
        </h2>
      </Reveal>
      <div className="mt-14 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {FEATURES.map((feature, index) => (
          <Reveal key={feature.title} delay={(index % 4) * 80}>
            <article className="group h-full rounded-2xl border border-border bg-card p-6 transition-all duration-300 hover:-translate-y-1 hover:border-primary/40 hover:shadow-[0_20px_50px_-25px_var(--primary)]">
              <span className="flex size-10 items-center justify-center rounded-xl bg-primary/10 transition-colors group-hover:bg-primary">
                <feature.icon
                  aria-hidden="true"
                  className="size-5 text-primary transition-colors group-hover:text-primary-foreground"
                />
              </span>
              <h3 className="mt-5 font-semibold">{feature.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{feature.text}</p>
            </article>
          </Reveal>
        ))}
      </div>
    </section>
  )
}
