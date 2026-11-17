import { Link } from 'react-router'
import PageHeader from '../components/layout/PageHeader.tsx'

function AdminPage() {
  return (
    <section>
      <PageHeader
        eyebrow="Administration"
        title="Administrator dashboard"
        description="Track term readiness, resolve missing assessment details, and follow up on policy gaps."
      />

      <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm text-cas-muted">No course planning data loaded yet.</p>
        <Link
          to="/admin/outline-review"
          className="inline-flex h-10 items-center justify-center rounded-lg bg-mcmaster-maroon px-4 text-sm font-semibold text-white hover:bg-mcmaster-maroon/90"
        >
          Upload course outlines
        </Link>
      </div>

      <div className="mb-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {[
          'Fully planned',
          'Incomplete courses',
          'Missing dates / weights',
          'Policy gaps',
        ].map((label) => (
          <article
            key={label}
            className="rounded-lg border border-cas-border bg-white p-5"
          >
            <p className="text-sm text-cas-muted">{label}</p>
            <p className="mt-1 text-3xl font-semibold text-cas-ink">—</p>
            <p className="mt-2 text-[11px] text-cas-muted">Awaiting uploaded outlines</p>
          </article>
        ))}
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.7fr)_minmax(280px,1fr)]">
        <article className="rounded-lg border border-cas-border bg-white p-5 sm:p-6">
          <h2 className="text-lg font-semibold text-cas-ink sm:text-[19px]">
            Course status overview
          </h2>
          <p className="mt-1 text-sm text-cas-muted">
            Resolve highlighted gaps before marking a course fully planned.
          </p>

          <div className="mt-4 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <label className="sr-only" htmlFor="course-search">
              Search courses
            </label>
            <input
              id="course-search"
              type="search"
              placeholder="Search course code or instructor…"
              className="h-10 w-full rounded-lg border border-cas-border bg-cas-surface px-3 text-sm text-cas-ink placeholder:text-cas-muted lg:max-w-md"
              disabled
            />
            <label className="sr-only" htmlFor="status-filter">
              Status filter
            </label>
            <select
              id="status-filter"
              className="h-10 rounded-lg border border-cas-border bg-white px-3 text-sm text-cas-ink lg:min-w-56"
              disabled
              defaultValue="all"
            >
              <option value="all">Status: All courses</option>
            </select>
          </div>

          <div className="mt-6 rounded-lg border border-dashed border-cas-border bg-cas-surface px-4 py-10 text-center">
            <p className="text-sm font-semibold text-cas-ink">No courses to show</p>
            <p className="mt-1 text-sm text-cas-muted">
              Upload course outlines to populate planning status.
            </p>
            <Link
              to="/admin/outline-review"
              className="mt-4 inline-block text-sm font-semibold text-mcmaster-maroon hover:underline"
            >
              Go to outline review →
            </Link>
          </div>
        </article>

        <aside className="rounded-lg border border-cas-border bg-white p-5 sm:p-6">
          <h2 className="text-lg font-semibold text-cas-ink sm:text-[19px]">
            Needs attention
          </h2>
          <p className="mt-1 text-sm text-cas-muted">Prioritize these review queues.</p>
          <p className="mt-8 text-sm text-cas-muted">
            Attention queues will appear here after outlines are reviewed.
          </p>
        </aside>
      </div>
    </section>
  )
}

export default AdminPage
