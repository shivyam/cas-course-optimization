// App shell: shared header/navigation plus the route table.
import { NavLink, Route, Routes } from 'react-router'
import AdminPage from './pages/AdminPage.tsx'
import HomePage from './pages/HomePage.tsx'
import InstructorPage from './pages/InstructorPage.tsx'

// Styles the nav link for the current page differently from the others.
function navLinkClass({ isActive }: { isActive: boolean }) {
  return isActive ? 'font-semibold text-mcmaster-gold' : 'text-white hover:underline'
}

function App() {
  return (
    <div className="min-h-screen">
      <header className="bg-mcmaster-maroon px-6 py-4 text-white">
        <nav className="flex items-center gap-6">
          <span className="text-lg font-bold">CAS Course Optimization</span>
          {/* `end` stops "/" from matching every route, so Home is only active on "/". */}
          <NavLink to="/" end className={navLinkClass}>
            Home
          </NavLink>
          <NavLink to="/admin" className={navLinkClass}>
            Admin
          </NavLink>
          <NavLink to="/instructor" className={navLinkClass}>
            Instructor
          </NavLink>
        </nav>
      </header>

      <main className="p-6">
        {/* Admin and Instructor are placeholders; real role checks come later. */}
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/admin" element={<AdminPage />} />
          <Route path="/instructor" element={<InstructorPage />} />
        </Routes>
      </main>
    </div>
  )
}

export default App
