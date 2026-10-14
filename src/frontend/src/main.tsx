// Browser entry point: mounts the React app into <div id="root"> in index.html.
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router'
import App from './App.tsx'
import './theme.css'

createRoot(document.getElementById('root')!).render(
  // StrictMode runs extra checks in development to surface common bugs.
  <StrictMode>
    {/* BrowserRouter lives here (not in App) so tests can use MemoryRouter instead. */}
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>,
)
