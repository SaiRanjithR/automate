import { Lock, ShieldCheck, UserCheck } from 'lucide-react'

import { StatusChip, type ComplianceStatus } from '@/components/common/StatusChip'
import { Reveal } from '@/features/landing/Reveal'

const ROWS: { id: string; text: string; status: ComplianceStatus; review: string }[] = [
  {
    id: 'R-4.2-02',
    text: 'Support HL7 FHIR R4 and ABDM milestones M1–M3',
    status: 'fully_compliant',
    review: '100',
  },
  {
    id: 'R-4.3-02',
    text: 'Train at least 500 hospital staff',
    status: 'fully_compliant',
    review: '95',
  },
  {
    id: 'R-4.1-01',
    text: 'Patient registration with ABHA linkage at every counter',
    status: 'partially_compliant',
    review: '80',
  },
  {
    id: 'R-5.7-01',
    text: 'No change in rates for implementation + 3 years',
    status: 'fully_compliant',
    review: '95',
  },
  {
    id: 'R-4.2-07',
    text: 'Integrate with the state SMS gateway on DLT',
    status: 'gap',
    review: '—',
  },
]

const POINTS = [
  {
    icon: ShieldCheck,
    title: 'Every claim has a source',
    text: 'File and page for each sentence; quotes are checked against the document.',
  },
  {
    icon: UserCheck,
    title: 'People approve every row',
    text: 'Serious review issues need a written reason before approval.',
  },
  {
    icon: Lock,
    title: 'Prices and signatures stay yours',
    text: 'The price sheet is left blank; the digital signature and upload are done by you.',
  },
]

export function MatrixPreview() {
  return (
    <section className="overflow-hidden bg-brand-ink py-24 text-white">
      <div className="mx-auto grid max-w-6xl items-center gap-14 px-6 lg:grid-cols-[1fr_1.15fr]">
        <Reveal>
          <p className="text-sm font-medium text-brand-glow">Trust, built in</p>
          <h2 className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">
            Fast, and honest about what it doesn’t know
          </h2>
          <ul className="mt-8 flex flex-col gap-6">
            {POINTS.map((point) => (
              <li key={point.title} className="flex gap-4">
                <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-white/10">
                  <point.icon aria-hidden="true" className="size-5 text-brand-glow" />
                </span>
                <div>
                  <h3 className="font-semibold">{point.title}</h3>
                  <p className="mt-1 text-sm text-white/65">{point.text}</p>
                </div>
              </li>
            ))}
          </ul>
        </Reveal>
        <Reveal delay={150} className="[perspective:1600px]">
          <div className="[transform:rotateX(10deg)_rotateY(-16deg)_rotateZ(1deg)] rounded-2xl border border-white/10 bg-background p-4 text-foreground shadow-[0_40px_120px_-40px_var(--primary)] transition-transform duration-700 hover:[transform:rotateX(0)_rotateY(0)_rotateZ(0)] motion-reduce:[transform:none]">
            <div className="mb-3 flex flex-wrap gap-2 text-xs">
              <span className="rounded-md border border-border px-2 py-1">36 requirements</span>
              <span className="rounded-md border border-status-full/50 px-2 py-1 text-status-full">
                22 compliant
              </span>
              <span className="rounded-md border border-status-partial/50 px-2 py-1 text-status-partial">
                10 partial
              </span>
              <span className="rounded-md border border-status-gap/60 px-2 py-1 font-semibold text-status-gap">
                4 gaps
              </span>
            </div>
            <div className="overflow-hidden rounded-lg border border-border">
              <div className="grid grid-cols-[5.5rem_1fr_6.5rem_3rem] bg-muted/60 px-3 py-2 text-xs font-medium text-muted-foreground">
                <span>ID</span>
                <span>Requirement</span>
                <span>Status</span>
                <span className="text-right">Review</span>
              </div>
              {ROWS.map((row, index) => (
                <div
                  key={row.id}
                  className={`grid grid-cols-[5.5rem_1fr_6.5rem_3rem] items-center gap-2 border-t border-border px-3 py-2.5 text-sm ${index === 1 ? 'bg-primary/8 shadow-[inset_3px_0_0_var(--primary)]' : ''}`}
                >
                  <span className="font-mono text-xs">{row.id}</span>
                  <span className="truncate">{row.text}</span>
                  <StatusChip status={row.status} />
                  <span className="text-right text-xs text-muted-foreground tabular-nums">
                    {row.review}
                  </span>
                </div>
              ))}
            </div>
            <p className="mt-3 font-serif text-xs text-muted-foreground">
              “We trained 450 hospital staff including doctors, nurses and administrators…” —
              Case_Studies.pdf · page 1
            </p>
          </div>
        </Reveal>
      </div>
    </section>
  )
}
