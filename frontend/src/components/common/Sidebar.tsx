import { BookOpen, Building2, FilePlus2, LayoutDashboard, LogOut, ShieldCheck } from 'lucide-react'
import { Link, NavLink, useNavigate } from 'react-router'

import { Button } from '@/components/ui/button'
import { useLogout, useMe } from '@/features/auth/api'
import { cn } from '@/lib/utils'

const NAV_ITEMS = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/company', label: 'Company profile', icon: Building2, end: false },
  { to: '/knowledge', label: 'Knowledge base', icon: BookOpen, end: false },
  { to: '/policies', label: 'Policies', icon: ShieldCheck, end: false },
] as const

export function Sidebar() {
  const { data: user } = useMe()
  const logout = useLogout()
  const navigate = useNavigate()
  return (
    <aside className="flex w-60 shrink-0 flex-col border-r border-sidebar-border bg-sidebar px-3 py-4 text-sidebar-foreground">
      <Link to="/dashboard" className="mb-6 flex items-center gap-2 px-2 text-base font-semibold">
        <span aria-hidden="true" className="size-6 rounded-md bg-primary" />
        BidReady
      </Link>
      <Button asChild className="mb-4 justify-start">
        <Link to="/projects/new">
          <FilePlus2 aria-hidden="true" />
          New project
        </Link>
      </Button>
      <nav aria-label="Main" className="flex flex-col gap-1">
        {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-2 rounded-md px-2 py-1.5 text-sm transition-colors hover:bg-sidebar-accent',
                isActive && 'bg-sidebar-accent font-medium text-sidebar-accent-foreground',
              )
            }
          >
            <Icon aria-hidden="true" className="size-4" />
            {label}
          </NavLink>
        ))}
      </nav>
      {user ? (
        <div className="mt-auto flex items-center gap-2 border-t border-sidebar-border px-2 pt-3 text-xs">
          <span className="truncate text-muted-foreground">{user.email}</span>
          <Button
            variant="ghost"
            size="icon-sm"
            className="ml-auto"
            aria-label="Sign out"
            onClick={() => logout.mutate(undefined, { onSuccess: () => void navigate('/login') })}
          >
            <LogOut />
          </Button>
        </div>
      ) : null}
    </aside>
  )
}
