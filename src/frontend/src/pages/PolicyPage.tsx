import PageHeader from '../components/layout/PageHeader.tsx'

function PolicyPage() {
  return (
    <section>
      <PageHeader
        eyebrow="Administration"
        title="Policy compliance & CEAB"
        description="Review course policy checks and learning-outcome mappings against the Master Course Sheet."
      />

      <div className="mb-5 flex flex-col gap-3 rounded-lg border border-cas-border bg-cas-surface px-4 py-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-4">
          <label className="sr-only" htmlFor="policy-course">
            Course
          </label>
          <select
            id="policy-course"
            className="h-10 rounded-md border border-cas-border bg-white px-3 text-base text-cas-muted"
            disabled
            defaultValue=""
          >
            <option value="">No courses available</option>
          </select>
          <p className="text-sm text-cas-muted">Select a course to begin review</p>
        </div>
        <p className="text-sm font-semibold text-cas-muted">0 policy gaps</p>
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(260px,0.85fr)_minmax(0,1.4fr)]">
        <article className="rounded-lg border border-cas-border bg-white p-5">
          <h2 className="text-lg font-semibold text-cas-ink sm:text-[19px]">
            McMaster policy checks
          </h2>
          <p className="mt-1 text-xs text-cas-muted">
            Checklist results will appear after an outline is reviewed.
          </p>
          <div className="mt-6 rounded-lg border border-dashed border-cas-border bg-cas-surface px-4 py-10 text-center text-sm text-cas-muted">
            No policy checks yet
          </div>
        </article>

        <article className="rounded-lg border border-cas-border bg-white p-5">
          <h2 className="text-lg font-semibold text-cas-ink sm:text-[19px]">
            CEAB Graduate Attribute mapping
          </h2>
          <p className="mt-1 text-xs text-cas-muted">
            Compare outline outcomes with the Master Course Sheet before confirming.
          </p>
          <div className="mt-6 rounded-lg border border-dashed border-cas-border bg-cas-surface px-4 py-10 text-center text-sm text-cas-muted">
            No CEAB mappings yet
          </div>
        </article>
      </div>
    </section>
  )
}

export default PolicyPage
