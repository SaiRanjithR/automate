import { FileCheck2, ListChecks, ScanSearch, Upload, type LucideIcon } from 'lucide-react'

import { Reveal } from '@/features/landing/Reveal'

const STEPS: { icon: LucideIcon; title: string; text: string }[] = [
  {
    icon: Upload,
    title: 'Upload the tender',
    text: 'Drop the RFP, its annexures and any corrigendum. PDF or Word, scanned pages included.',
  },
  {
    icon: ScanSearch,
    title: 'Everything is extracted',
    text: 'Requirements, deadline, EMD, page limits, file naming, eligibility and how bids are scored.',
  },
  {
    icon: ListChecks,
    title: 'Draft and review',
    text: 'Answers come from your past proposals with citations. Each one is reviewed; you approve.',
  },
  {
    icon: FileCheck2,
    title: 'Download the package',
    text: 'Covering letter, technical proposal, compliance matrix, filled forms and checklist, ready to sign.',
  },
]

export function HowItWorks() {
  return (
    <section id="how-it-works" className="scroll-mt-20 bg-muted/40 py-24">
      <div className="mx-auto max-w-6xl px-6">
        <Reveal className="max-w-2xl">
          <p className="text-sm font-medium text-primary">How it works</p>
          <h2 className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">
            Four steps from PDF to bid
          </h2>
        </Reveal>
        <div className="relative mt-14">
          <div
            aria-hidden="true"
            className="absolute top-7 right-[12%] left-[12%] hidden h-px bg-linear-to-r from-primary/0 via-primary/50 to-primary/0 md:block"
          />
          <ol className="grid gap-6 md:grid-cols-4">
            {STEPS.map((step, index) => (
              <li key={step.title}>
                <Reveal delay={index * 110} className="relative flex flex-col items-start gap-4">
                  <span className="relative flex size-14 items-center justify-center rounded-2xl border border-primary/30 bg-background shadow-[0_10px_30px_-12px_var(--primary)]">
                    <step.icon aria-hidden="true" className="size-6 text-primary" />
                    <span className="absolute -top-2 -right-2 flex size-6 items-center justify-center rounded-full bg-primary font-mono text-xs text-primary-foreground">
                      {index + 1}
                    </span>
                  </span>
                  <h3 className="text-base font-semibold">{step.title}</h3>
                  <p className="text-sm text-muted-foreground">{step.text}</p>
                </Reveal>
              </li>
            ))}
          </ol>
        </div>
      </div>
    </section>
  )
}
