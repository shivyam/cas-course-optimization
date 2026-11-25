// Runs before every test file (configured in vite.config.ts).
import '@testing-library/jest-dom/vitest' // adds matchers like toBeInTheDocument()
import { cleanup } from '@testing-library/react'
import { afterEach, vi } from 'vitest'

// pdfjs-dist touches DOMMatrix at import time; jsdom does not provide it.
if (typeof globalThis.DOMMatrix === 'undefined') {
  // Minimal stub — enough for the module to load in unit tests.
  globalThis.DOMMatrix = class DOMMatrix {} as unknown as typeof DOMMatrix
}

afterEach(() => {
  // Unmount rendered components and undo any mocked globals (e.g. fetch)
  // so tests do not leak state into each other.
  cleanup()
  vi.unstubAllGlobals()
})
