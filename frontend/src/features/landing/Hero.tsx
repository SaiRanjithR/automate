import { ArrowRight, Sparkles } from 'lucide-react'
import { lazy, Suspense } from 'react'
import { Link } from 'react-router'

import { Button } from '@/components/ui/button'
import { SceneBoundary } from '@/features/landing/SceneBoundary'
import { useMediaQuery, useReducedMotion } from '@/features/landing/useReducedMotion'

const HeroScene = lazy(() => import('@/features/landing/HeroScene'))

const STATS = [
  { value: '97%', label: 'requirement recall on our labelled tender' },
  { value: '11', label: 'ready-to-sign files per bid' },
  { value: '0', label: 'claims without a source' },
]

function SceneFallback() {
  return (
    <div aria-hidden="true" className="flex h-full items-center justify-center">
      <div className="size-48 rounded-full bg-primary/30 blur-3xl" />
    </div>
  )
}

export function Hero({ appHref, appLabel }: { appHref: string; appLabel: string }) {
  const reducedMotion = useReducedMotion()
  const desktop = useMediaQuery('(min-width: 1024px)')
  const scene = (
    <SceneBoundary fallback={<SceneFallback />}>
      <Suspense fallback={<SceneFallback />}>
        <HeroScene reducedMotion={reducedMotion} />
      </Suspense>
    </SceneBoundary>
  )
  return (
    <section className="relative isolate overflow-hidden bg-brand-ink text-white">
      <div
        aria-hidden="true"
        className="absolute inset-0 -z-20 bg-[radial-gradient(ellipse_at_70%_20%,var(--color-brand-deep),transparent_65%),radial-gradient(ellipse_at_10%_90%,color-mix(in_oklch,var(--primary)_35%,transparent),transparent_55%)]"
      />
      <div
        aria-hidden="true"
        className="absolute inset-0 -z-10 bg-[linear-gradient(to_right,rgb(255_255_255/0.05)_1px,transparent_1px),linear-gradient(to_bottom,rgb(255_255_255/0.05)_1px,transparent_1px)] mask-[radial-gradient(ellipse_at_center,black,transparent_75%)] bg-size-[56px_56px]"
      />
      {desktop ? <div className="absolute inset-0 left-[38%] -z-10">{scene}</div> : null}

      <div className="mx-auto flex min-h-[calc(100svh-4rem)] max-w-7xl items-center px-6 pt-24 pb-20">
        <div className="max-w-xl">
          <p className="mb-5 inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/5 px-3 py-1 text-xs text-white/80 backdrop-blur">
            <Sparkles aria-hidden="true" className="size-3.5 text-brand-glow" />
            Built for GeM, CPPP, state portals and private RFPs
          </p>
          <h1 className="text-4xl leading-[1.08] font-semibold tracking-tight text-balance sm:text-5xl lg:text-6xl">
            Turn any tender into a{' '}
            <span className="bg-linear-to-r from-brand-glow via-white to-status-full bg-clip-text text-transparent">
              ready-to-sign bid
            </span>{' '}
            in minutes.
          </h1>
          <p className="mt-6 max-w-lg text-lg text-pretty text-white/70">
            BidReady reads the RFP, finds every requirement, drafts answers from your own past
            proposals with a source for every claim, and packages the files exactly as the tender
            demands.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Button
              asChild
              size="lg"
              className="h-11 bg-white px-5 text-brand-ink hover:bg-white/90"
            >
              <Link to={appHref}>
                {appLabel}
                <ArrowRight aria-hidden="true" />
              </Link>
            </Button>
            <Button
              asChild
              size="lg"
              variant="outline"
              className="h-11 border-white/25 bg-white/5 px-5 text-white hover:bg-white/10 hover:text-white"
            >
              <a href="#how-it-works">See how it works</a>
            </Button>
          </div>
          <dl className="mt-12 grid max-w-lg grid-cols-3 gap-6 border-t border-white/10 pt-6">
            {STATS.map((stat) => (
              <div key={stat.label}>
                <dt className="sr-only">{stat.label}</dt>
                <dd className="text-3xl font-semibold tabular-nums">{stat.value}</dd>
                <dd className="mt-1 text-xs leading-snug text-white/60">{stat.label}</dd>
              </div>
            ))}
          </dl>
          {desktop ? null : <div className="-mx-6 mt-8 h-80">{scene}</div>}
        </div>
      </div>
    </section>
  )
}
