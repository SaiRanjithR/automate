import { Link } from 'react-router'

import { Button } from '@/components/ui/button'
import { useMe } from '@/features/auth/api'
import { BeforeAfter } from '@/features/landing/BeforeAfter'
import { Closing } from '@/features/landing/Closing'
import { Features } from '@/features/landing/Features'
import { Hero } from '@/features/landing/Hero'
import { HowItWorks } from '@/features/landing/HowItWorks'
import { MatrixPreview } from '@/features/landing/MatrixPreview'

export function LandingPage() {
  const { data: user } = useMe()
  const appHref = user ? '/dashboard' : '/login?next=%2Fdashboard'
  const appLabel = user ? 'Open dashboard' : 'Get started'

  return (
    <div className="min-h-svh bg-background">
      <header className="absolute inset-x-0 top-0 z-20">
        <nav
          aria-label="Landing"
          className="mx-auto flex h-16 max-w-7xl items-center justify-between px-6 text-white"
        >
          <Link to="/" className="flex items-center gap-2 text-base font-semibold">
            <span
              aria-hidden="true"
              className="size-6 rounded-md bg-primary shadow-[0_0_20px_var(--primary)]"
            />
            BidReady
          </Link>
          <div className="flex items-center gap-1 sm:gap-6">
            <a
              href="#how-it-works"
              className="hidden text-sm text-white/70 hover:text-white sm:inline"
            >
              How it works
            </a>
            <a href="#features" className="hidden text-sm text-white/70 hover:text-white sm:inline">
              Features
            </a>
            <Button
              asChild
              size="sm"
              variant="outline"
              className="border-white/25 bg-white/5 text-white hover:bg-white/10 hover:text-white"
            >
              <Link to={appHref}>{user ? 'Dashboard' : 'Sign in'}</Link>
            </Button>
          </div>
        </nav>
      </header>
      <main>
        <Hero appHref={appHref} appLabel={appLabel} />
        <BeforeAfter />
        <HowItWorks />
        <MatrixPreview />
        <Features />
        <Closing appHref={appHref} appLabel={appLabel} />
      </main>
    </div>
  )
}
