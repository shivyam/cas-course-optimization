// Landing page. Calls the backend health check to show whether the API is reachable.
import { useEffect, useState } from 'react'
import { Link } from 'react-router'

type HealthStatus = 'loading' | 'ok' | 'error'

// Base URL for API calls. Defaults to /api, which the Vite dev proxy forwards to
// the backend (see vite.config.ts). Override with VITE_API_BASE_URL in .env.
const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? '/api'

// Text shown to the user for each health status.
const statusMessages: Record<HealthStatus, string> = {
  loading: 'Checking backend...',
  ok: 'Backend is reachable',
  error: 'Backend is not reachable',
}

function HomePage() {
  const [status, setStatus] = useState<HealthStatus>('loading')

  useEffect(() => {
    // Abort the request if the page unmounts before it finishes.
    const controller = new AbortController()

    fetch(`${apiBaseUrl}/health`, { signal: controller.signal })
      .then((response) => (response.ok ? response.json() : Promise.reject()))
      .then((body: { status?: string }) =>
        setStatus(body.status === 'ok' ? 'ok' : 'error'),
      )
      .catch(() => {
        // Ignore the error caused by our own abort; anything else means unreachable.
        if (!controller.signal.aborted) setStatus('error')
      })

    return () => controller.abort()
  }, [])

  return (
    <div className="min-h-screen bg-white">
      <header className="bg-mcmaster-maroon px-4 py-4 text-white sm:px-8">
        <div className="mx-auto flex max-w-[1440px] items-center justify-between gap-4">
          <span className="text-lg font-semibold">CAS Course Optimization</span>
          <nav className="flex items-center gap-4 text-sm sm:gap-5">
            <Link to="/" className="font-semibold text-mcmaster-gold">
              Home
            </Link>
            <Link to="/admin" className="text-white hover:text-mcmaster-gold">
              Admin
            </Link>
            <Link to="/instructor" className="text-white hover:text-mcmaster-gold">
              Instructor
            </Link>
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-3xl px-4 py-10 sm:px-8 sm:py-16">
        <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-mcmaster-maroon">
          CAS Course Optimization
        </p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight text-cas-ink sm:text-4xl">
          CAS Midterm and Assignment Optimization
        </h1>
        <p className="mt-4 text-base leading-relaxed text-cas-muted">
          Choose a workspace below to upload course outlines, review calendars, resolve
          workload conflicts, and check policy compliance.
        </p>

        <div className="mt-8 grid gap-3 sm:grid-cols-2">
          <Link
            to="/admin"
            className="rounded-lg border border-cas-border bg-white p-5 hover:border-mcmaster-maroon"
          >
            <p className="text-sm font-semibold text-mcmaster-maroon">Admin</p>
            <p className="mt-1 text-sm text-cas-muted">
              Dashboard, outline review, calendar, and policy compliance.
            </p>
          </Link>
          <Link
            to="/instructor"
            className="rounded-lg border border-cas-border bg-white p-5 hover:border-mcmaster-maroon"
          >
            <p className="text-sm font-semibold text-mcmaster-maroon">Instructor</p>
            <p className="mt-1 text-sm text-cas-muted">
              Workload conflicts and date recommendations.
            </p>
          </Link>
        </div>

        <p
          role="status"
          className={`mt-8 text-sm ${status === 'error' ? 'text-red-700' : 'text-cas-muted'}`}
        >
          {statusMessages[status]}
        </p>
      </main>
    </div>
  )
}

export default HomePage
