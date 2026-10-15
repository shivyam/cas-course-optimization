// Runs before every test file (configured in vite.config.ts).
import '@testing-library/jest-dom/vitest' // adds matchers like toBeInTheDocument()
import { cleanup } from '@testing-library/react'
import { afterEach, vi } from 'vitest'

afterEach(() => {
  // Unmount rendered components and undo any mocked globals (e.g. fetch)
  // so tests do not leak state into each other.
  cleanup()
  vi.unstubAllGlobals()
})
