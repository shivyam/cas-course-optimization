// App shell: shared header/navigation plus the route table.
import { Route, Routes } from 'react-router'
import AppShell from './components/layout/AppShell.tsx'
import AdminPage from './pages/AdminPage.tsx'
import CalendarPage from './pages/CalendarPage.tsx'
import HomePage from './pages/HomePage.tsx'
import InstructorPage from './pages/InstructorPage.tsx'
import OutlinePreviewPage from './pages/OutlinePreviewPage.tsx'
import OutlineReviewPage from './pages/OutlineReviewPage.tsx'
import PolicyPage from './pages/PolicyPage.tsx'

function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />

      {/* Shared workspace chrome for admin + instructor wireframe screens. */}
      <Route element={<AppShell />}>
        <Route path="/admin" element={<AdminPage />} />
        <Route path="/admin/outline-review" element={<OutlineReviewPage />} />
        <Route path="/admin/outline-preview" element={<OutlinePreviewPage />} />
        <Route path="/admin/calendar" element={<CalendarPage />} />
        <Route path="/admin/policy" element={<PolicyPage />} />
        <Route path="/instructor" element={<InstructorPage />} />
      </Route>
    </Routes>
  )
}

export default App
