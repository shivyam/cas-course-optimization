// Smoke tests: the app renders, routing works, and the health check result is shown.
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { describe, expect, it, vi } from 'vitest'
import App from '../App.tsx'

// Render the app at a given URL. MemoryRouter keeps routing in memory (no browser).
function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  )
}

describe('App', () => {
  it('shows the landing page and reports the backend as reachable', async () => {
    // Fake a successful /api/health response so the test needs no running backend.
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: true, json: async () => ({ status: 'ok' }) }),
    )

    renderAt('/')

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(
      'CAS Midterm and Assignment Optimization',
    )
    // findBy* waits for the fetch to resolve and the status text to update.
    expect(await screen.findByText('Backend is reachable')).toBeInTheDocument()
  })

  it('shows an error when the backend cannot be reached', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))

    renderAt('/')

    expect(await screen.findByText('Backend is not reachable')).toBeInTheDocument()
  })

  it.each([
    ['/admin', 'Admin'],
    ['/instructor', 'Instructor'],
  ])('renders the placeholder page at %s', (path, heading) => {
    renderAt(path)

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(heading)
  })
})
