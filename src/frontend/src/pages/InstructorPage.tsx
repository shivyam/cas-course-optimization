import PageHeader from '../components/layout/PageHeader.tsx'

function InstructorPage() {
  return (
    <section>
      <PageHeader
        eyebrow="Instructor / Scheduling"
        title="Workload conflicts & recommendations"
        description="Review workload clusters and consider alternative dates before making a change."
      />

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.25fr)_minmax(300px,0.95fr)]">
        <div className="space-y-4">
          <div className="rounded-lg border border-cas-border bg-cas-surface px-4 py-3">
            <label className="sr-only" htmlFor="cohort-filter">
              Cohort
            </label>
            <select
              id="cohort-filter"
              className="h-10 w-full rounded-md border border-cas-border bg-white px-3 text-sm text-cas-muted sm:max-w-md"
              disabled
              defaultValue=""
            >
              <option value="">No cohorts available</option>
            </select>
          </div>

          <article className="rounded-lg border border-dashed border-cas-border bg-white p-5">
            <h2 className="text-lg font-semibold text-cas-ink">Workload clusters</h2>
            <p className="mt-2 text-sm text-cas-muted">
              Flagged assessment clusters will appear here once shared planning data is
              available.
            </p>
          </article>

          <article className="rounded-lg border border-dashed border-cas-border bg-white p-5">
            <h2 className="text-[17px] font-semibold text-cas-ink">
              Assessments contributing to this cluster
            </h2>
            <p className="mt-4 text-sm text-cas-muted">No cluster selected</p>
          </article>
        </div>

        <aside className="rounded-lg border border-dashed border-cas-border bg-white p-5 sm:p-6">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-mcmaster-maroon">
            Date recommendation
          </p>
          <h2 className="mt-2 text-xl font-semibold text-cas-ink">
            No recommendation yet
          </h2>
          <p className="mt-2 text-sm text-cas-muted">
            Date suggestions and workload comparisons will appear here after a conflict is
            selected.
          </p>
        </aside>
      </div>
    </section>
  )
}

export default InstructorPage
