import { Link } from 'react-router'
import PageHeader from '../components/layout/PageHeader.tsx'

const weekdays = [
  'Monday',
  'Tuesday',
  'Wednesday',
  'Thursday',
  'Friday',
  'Saturday',
  'Sunday',
]

function CalendarPage() {
  return (
    <section>
      <PageHeader
        eyebrow="Administration"
        title="Shared academic calendar"
        description="Compare assessment deadlines across courses and identify busy weeks."
      />

      <div className="mb-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {['Program', 'Year level', 'Course code', 'Date status'].map((label) => (
          <label key={label} className="block space-y-1.5">
            <span className="text-[11px] font-semibold text-cas-muted">{label}</span>
            <select
              className="h-[42px] w-full rounded-md border border-cas-border bg-white px-3 text-sm text-cas-muted"
              disabled
              defaultValue=""
            >
              <option value="">No options yet</option>
            </select>
          </label>
        ))}
      </div>

      <div className="mb-3 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <h2 className="text-2xl font-semibold text-cas-ink">Calendar</h2>
        <div className="flex flex-wrap items-center gap-4 text-xs text-mcmaster-maroon">
          <span>■ Confirmed</span>
          <span>┄ Tentative / not final</span>
        </div>
      </div>

      <div className="mb-4 hidden overflow-hidden rounded border border-cas-border md:block">
        <div className="grid grid-cols-7 border-b border-cas-border bg-cas-surface">
          {weekdays.map((day) => (
            <div
              key={day}
              className="border-r border-cas-border px-2 py-2.5 text-xs font-semibold text-cas-muted last:border-r-0 lg:px-3"
            >
              <span className="lg:hidden">{day.slice(0, 3)}</span>
              <span className="hidden lg:inline">{day}</span>
            </div>
          ))}
        </div>
        <div className="flex min-h-64 items-center justify-center bg-cas-surface px-4 py-12 text-center">
          <div>
            <p className="text-sm font-semibold text-cas-ink">No assessments scheduled</p>
            <p className="mt-1 text-sm text-cas-muted">
              Confirmed and tentative dates will appear here after outlines are reviewed.
            </p>
          </div>
        </div>
      </div>

      <div className="mb-4 rounded-lg border border-dashed border-cas-border bg-cas-surface px-4 py-10 text-center md:hidden">
        <p className="text-sm font-semibold text-cas-ink">No assessments scheduled</p>
        <p className="mt-1 text-sm text-cas-muted">
          Agenda items will appear here once planning data is available.
        </p>
      </div>

      <div className="flex flex-col gap-2 rounded bg-cas-surface px-4 py-3 text-xs sm:flex-row sm:items-center sm:justify-between">
        <p className="text-cas-muted">0 confirmed + 0 tentative shown</p>
        <Link
          to="/admin/outline-review"
          className="font-semibold text-mcmaster-maroon hover:underline"
        >
          Upload outlines →
        </Link>
      </div>
    </section>
  )
}

export default CalendarPage
