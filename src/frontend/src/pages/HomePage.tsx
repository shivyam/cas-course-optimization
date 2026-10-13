// Landing page. Calls the backend health check to show whether the API is reachable.
import { useEffect, useState } from 'react'

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
    <section className="space-y-4">
      <h1 className="text-2xl font-bold text-mcmaster-maroon">
        CAS Midterm and Assignment Optimization
      </h1>
      <p className="text-mcmaster-grey">
        Choose Admin or Instructor from the navigation bar to get started.
      </p>
      {/* role="status" lets screen readers announce the result when it changes. */}
      <p role="status" className={status === 'error' ? 'text-red-700' : 'text-gray-700'}>
        {statusMessages[status]}
      </p>
    </section>
  )
}

export default HomePage
