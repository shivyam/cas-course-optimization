import { useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router'

type WorkspaceTab = {
  to: string
  label: string
  end?: boolean
}

const workspaceTabs: WorkspaceTab[] = [
  { to: '/admin', label: 'Overview', end: true },
  { to: '/admin/outline-review', label: 'Outline review' },
  { to: '/admin/calendar', label: 'Calendar' },
  { to: '/instructor', label: 'Workload & scheduling', end: true },
  { to: '/admin/policy', label: 'Policy & CEAB' },
]

function mainNavClass({ isActive }: { isActive: boolean }) {
  return isActive
    ? 'font-semibold text-mcmaster-gold'
    : 'text-white hover:text-mcmaster-gold/90'
}

function workspaceTabClass({ isActive }: { isActive: boolean }) {
  return [
    'relative shrink-0 whitespace-nowrap border-b-[3px] px-1 pb-3 pt-4 text-sm transition',
    isActive
      ? 'border-mcmaster-maroon font-semibold text-mcmaster-maroon'
      : 'border-transparent text-cas-muted hover:text-cas-ink',
  ].join(' ')
}

function AppShell() {
  const [mobileNavOpen, setMobileNavOpen] = useState(false)
  const { pathname } = useLocation()
  const roleLabel = pathname.startsWith('/instructor') ? 'Faculty professor' : 'CAS Admin'

  return (
    <div className="flex min-h-screen flex-col bg-white">
      <header className="bg-mcmaster-maroon text-white">
        <div className="mx-auto flex max-w-[1440px] items-center justify-between gap-4 px-4 py-4 sm:px-8">
          <div className="flex min-w-0 items-center gap-4 sm:gap-6">
            <span className="truncate text-base font-semibold sm:text-lg">
              CAS Course Optimization
            </span>
            <nav
              className="hidden items-center gap-5 text-sm md:flex"
              aria-label="Primary"
            >
              <NavLink to="/" end className={mainNavClass}>
                Home
              </NavLink>
              <NavLink to="/admin" className={mainNavClass}>
                Admin
              </NavLink>
              <NavLink to="/instructor" className={mainNavClass}>
                Instructor
              </NavLink>
            </nav>
          </div>

          <div className="flex items-center gap-3">
            <span className="hidden text-sm text-white/90 sm:inline">{roleLabel}</span>
            <button
              type="button"
              className="rounded-md border border-white/30 px-3 py-1.5 text-sm md:hidden"
              aria-expanded={mobileNavOpen}
              aria-controls="mobile-primary-nav"
              onClick={() => setMobileNavOpen((open) => !open)}
            >
              Menu
            </button>
          </div>
        </div>

        {mobileNavOpen && (
          <nav
            id="mobile-primary-nav"
            className="flex flex-col gap-2 border-t border-white/20 px-4 py-3 text-sm md:hidden"
            aria-label="Primary mobile"
          >
            <NavLink
              to="/"
              end
              className={mainNavClass}
              onClick={() => setMobileNavOpen(false)}
            >
              Home
            </NavLink>
            <NavLink
              to="/admin"
              className={mainNavClass}
              onClick={() => setMobileNavOpen(false)}
            >
              Admin
            </NavLink>
            <NavLink
              to="/instructor"
              className={mainNavClass}
              onClick={() => setMobileNavOpen(false)}
            >
              Instructor
            </NavLink>
          </nav>
        )}
      </header>

      <div className="sticky top-0 z-20 border-b border-cas-border bg-white">
        <nav
          className="mx-auto flex max-w-[1440px] gap-4 overflow-x-auto px-4 [-ms-overflow-style:none] [scrollbar-width:none] sm:gap-6 sm:px-8 [&::-webkit-scrollbar]:hidden"
          aria-label="Workspace"
        >
          {workspaceTabs.map((tab) => (
            <NavLink key={tab.to} to={tab.to} end={tab.end} className={workspaceTabClass}>
              {tab.label}
            </NavLink>
          ))}
        </nav>
      </div>

      <main className="mx-auto w-full max-w-[1440px] flex-1 px-4 py-6 sm:px-8 sm:py-8">
        <Outlet />
      </main>
    </div>
  )
}

export default AppShell
