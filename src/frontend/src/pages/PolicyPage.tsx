import { useMemo, useState, type ReactNode } from 'react'
import OutlinePdfViewer from '../components/OutlinePdfViewer.tsx'
import type { PdfHighlight } from '../components/OutlinePdfViewer.tsx'
import PageHeader from '../components/layout/PageHeader.tsx'

const demoCourse = {
  code: 'COMPSCI 2C03',
  title: 'Data Structures and Algorithms',
  instructor: 'Vincent Maccio',
  term: 'Fall 2026',
  outlineUrl: '/demo/COMPSCI2C03-VincentMaccio_Fall2026.pdf',
}

/** Visible rows before the check list scrolls. */
const visibleChecks = 3

type PolicyGap = {
  id: string
  page: number
  label: string
  detail: string
  marker: string
  highlights: PdfHighlight[]
}

type CeabGap = {
  id: string
  label: string
  detail: string
  page?: number
  highlights?: PdfHighlight[]
}

const policyGaps: PolicyGap[] = [
  {
    id: 'ta-c01',
    page: 1,
    label: 'Teaching Assistants (C01)',
    detail: 'Listed as “? TBD” — TA names and contact details are incomplete.',
    marker: '? TBD',
    highlights: [
      { x0: 136.82, y0: 588.9, x1: 141.16, y1: 598.86 },
      { x0: 144.07, y0: 588.9, x1: 162.86, y1: 598.86 },
    ],
  },
  {
    id: 'tutorial-t05',
    page: 2,
    label: 'Tutorial T05 location',
    detail: 'Room is marked “?” (Monday 11:30AM–12:20PM).',
    marker: '?',
    highlights: [{ x0: 281.93, y0: 124.38, x1: 286.26, y1: 134.34 }],
  },
  {
    id: 'tutorial-t06',
    page: 2,
    label: 'Tutorial T06 location',
    detail: 'Room is marked “?” (Tuesday 9:30AM–10:20PM).',
    marker: '?',
    highlights: [{ x0: 277.71, y0: 140.32, x1: 282.04, y1: 150.28 }],
  },
  {
    id: 'office-hours',
    page: 2,
    label: 'Office hours',
    detail: 'Listed as “? TBD” instead of a concrete time and place.',
    marker: '? TBD',
    highlights: [
      { x0: 136.82, y0: 168.22, x1: 141.16, y1: 178.18 },
      { x0: 144.07, y0: 168.22, x1: 162.86, y1: 178.18 },
    ],
  },
  {
    id: 'ta-extra',
    page: 2,
    label: 'Teaching Assistants',
    detail: 'An additional TA entry is left as “TBD”.',
    marker: 'TBD',
    highlights: [{ x0: 136.53, y0: 243.93, x1: 155.32, y1: 253.89 }],
  },
]

const ceabGaps: CeabGap[] = [
  {
    id: 'missing-ga',
    label: 'Graduate Attributes section missing',
    detail:
      'This outline has no CEAB graduate-attribute mapping to compare against the Master Course Sheet.',
    page: 2,
  },
  {
    id: 'kb-unmapped',
    label: 'Knowledge Base (KB) unmapped',
    detail:
      'Master Course Sheet expects KB indicators; none are declared in the outline learning objectives.',
    page: 2,
  },
  {
    id: 'pa-unmapped',
    label: 'Problem Analysis (PA) unmapped',
    detail:
      'No PA graduate-attribute indicators are linked to assessments or learning outcomes.',
    page: 2,
  },
  {
    id: 'use-unmapped',
    label: 'Use of Engineering Tools (UT) unmapped',
    detail:
      'Course uses C++ / Java libraries, but UT indicators are not recorded for CEAB reporting.',
    page: 2,
  },
]

type SelectedCheck = {
  id: string
  source: 'policy' | 'ceab'
  label: string
  page: number
  marker?: string
  highlights: PdfHighlight[]
}

function buildSelection(id: string, source: 'policy' | 'ceab'): SelectedCheck | null {
  if (source === 'policy') {
    const gap = policyGaps.find((item) => item.id === id)
    if (!gap) return null
    return {
      id: gap.id,
      source,
      label: gap.label,
      page: gap.page,
      marker: gap.marker,
      highlights: gap.highlights,
    }
  }

  const gap = ceabGaps.find((item) => item.id === id)
  if (!gap) return null
  return {
    id: gap.id,
    source,
    label: gap.label,
    page: gap.page ?? 1,
    highlights: gap.highlights ?? [],
  }
}

/** Mark a flagged check as a false positive (dismissed for this review). */
function markFalsePositive(overrides: ReadonlySet<string>, checkId: string): Set<string> {
  const next = new Set(overrides)
  next.add(checkId)
  return next
}

/** Clear a false-positive override and restore the check as an active gap. */
function clearFalsePositive(
  overrides: ReadonlySet<string>,
  checkId: string,
): Set<string> {
  const next = new Set(overrides)
  next.delete(checkId)
  return next
}

function PolicyPage() {
  const [selected, setSelected] = useState<SelectedCheck>(() =>
    buildSelection(policyGaps[0].id, 'policy')!,
  )
  const [falsePositives, setFalsePositives] = useState<Set<string>>(() => new Set())

  const activePolicyGaps = useMemo(
    () => policyGaps.filter((gap) => !falsePositives.has(gap.id)),
    [falsePositives],
  )
  const activeCeabGaps = useMemo(
    () => ceabGaps.filter((gap) => !falsePositives.has(gap.id)),
    [falsePositives],
  )
  const gapCount = activePolicyGaps.length + activeCeabGaps.length
  const selectedIsFalsePositive = falsePositives.has(selected.id)

  function selectCheck(id: string, source: 'policy' | 'ceab') {
    const next = buildSelection(id, source)
    if (next) setSelected(next)
  }

  function overrideAsFalsePositive(checkId: string) {
    setFalsePositives((current) => markFalsePositive(current, checkId))
  }

  function restoreCheck(checkId: string) {
    setFalsePositives((current) => clearFalsePositive(current, checkId))
  }

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
            className="h-10 rounded-md border border-cas-border bg-white px-3 text-base text-cas-ink"
            defaultValue={demoCourse.code}
          >
            <option value={demoCourse.code}>
              {demoCourse.code} — {demoCourse.instructor} ({demoCourse.term})
            </option>
          </select>
          <p className="text-sm text-cas-muted">
            Click a check to highlight it in the outline. Override false positives when a
            flag is incorrect.
          </p>
        </div>
        <p className="text-sm font-semibold text-mcmaster-maroon">
          {gapCount} active policy gaps
          {falsePositives.size > 0 ? (
            <span className="ml-2 font-normal text-cas-muted">
              ({falsePositives.size} overridden)
            </span>
          ) : null}
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(280px,0.9fr)_minmax(0,1.35fr)]">
        <div className="space-y-6">
          <CheckListCard
            title="McMaster policy checks"
            description={`Incomplete fields flagged in the ${demoCourse.code} outline PDF.`}
            visibleCount={visibleChecks}
            totalCount={policyGaps.length}
            activeCount={activePolicyGaps.length}
          >
            {policyGaps.map((gap) => (
              <CheckRow
                key={gap.id}
                selected={selected.id === gap.id}
                overridden={falsePositives.has(gap.id)}
                label={gap.label}
                badge={gap.marker}
                detail={`Page ${gap.page}: ${gap.detail}`}
                onSelect={() => selectCheck(gap.id, 'policy')}
                onMarkFalsePositive={() => overrideAsFalsePositive(gap.id)}
                onClearFalsePositive={() => restoreCheck(gap.id)}
              />
            ))}
          </CheckListCard>

          <CheckListCard
            title="CEAB Graduate Attribute mapping"
            description="Compare outline outcomes with the Master Course Sheet before confirming."
            visibleCount={visibleChecks}
            totalCount={ceabGaps.length}
            activeCount={activeCeabGaps.length}
          >
            {ceabGaps.map((gap) => (
              <CheckRow
                key={gap.id}
                selected={selected.id === gap.id}
                overridden={falsePositives.has(gap.id)}
                label={gap.label}
                detail={gap.detail}
                onSelect={() => selectCheck(gap.id, 'ceab')}
                onMarkFalsePositive={() => overrideAsFalsePositive(gap.id)}
                onClearFalsePositive={() => restoreCheck(gap.id)}
              />
            ))}
          </CheckListCard>
        </div>

        <article className="rounded-lg border border-cas-border bg-white p-5 lg:sticky lg:top-4 lg:self-start">
          <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <h2 className="text-lg font-semibold text-cas-ink sm:text-[19px]">
                Highlighted outline
              </h2>
              <p className="mt-1 text-xs text-cas-muted">
                {demoCourse.code} · {selected.label}
                {selected.marker ? ` · “${selected.marker}”` : ''}
                {selectedIsFalsePositive ? ' · overridden as false positive' : ''}
              </p>
            </div>
            <a
              href={`${demoCourse.outlineUrl}#page=${selected.page}`}
              target="_blank"
              rel="noreferrer"
              className="text-sm font-semibold text-mcmaster-maroon hover:underline"
            >
              Open PDF in new tab →
            </a>
          </div>

          <div className="h-[min(75vh,52rem)]">
            <OutlinePdfViewer
              url={demoCourse.outlineUrl}
              page={selected.page}
              highlights={selectedIsFalsePositive ? [] : selected.highlights}
              focusLabel={selected.label}
            />
          </div>
        </article>
      </div>
    </section>
  )
}

type CheckListCardProps = {
  title: string
  description: string
  visibleCount: number
  totalCount: number
  activeCount: number
  children: ReactNode
}

function CheckListCard({
  title,
  description,
  visibleCount,
  totalCount,
  activeCount,
  children,
}: CheckListCardProps) {
  return (
    <article className="rounded-lg border border-cas-border bg-white p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-cas-ink sm:text-[19px]">{title}</h2>
          <p className="mt-1 text-xs text-cas-muted">{description}</p>
        </div>
        <p className="shrink-0 text-[11px] font-semibold text-cas-muted">
          {activeCount} active
        </p>
      </div>
      <div
        className="mt-4 max-h-[21.5rem] space-y-3 overflow-y-auto pr-1"
        style={{ scrollbarGutter: 'stable' }}
        aria-label={`${title}, showing ${Math.min(visibleCount, totalCount)} of ${totalCount}`}
      >
        {children}
      </div>
      {totalCount > visibleCount ? (
        <p className="mt-2 text-[11px] text-cas-muted">
          Showing {visibleCount} at a time — scroll for {totalCount - visibleCount} more
        </p>
      ) : null}
    </article>
  )
}

type CheckRowProps = {
  selected: boolean
  overridden: boolean
  label: string
  detail: string
  badge?: string
  onSelect: () => void
  onMarkFalsePositive: () => void
  onClearFalsePositive: () => void
}

function CheckRow({
  selected,
  overridden,
  label,
  detail,
  badge,
  onSelect,
  onMarkFalsePositive,
  onClearFalsePositive,
}: CheckRowProps) {
  return (
    <div
      className={
        overridden
          ? 'rounded-lg border border-cas-border bg-cas-faint px-3 py-3'
          : selected
            ? 'rounded-lg border border-mcmaster-maroon bg-cas-tint px-3 py-3'
            : 'rounded-lg border border-cas-warning bg-cas-warning/40 px-3 py-3'
      }
    >
      <button
        type="button"
        onMouseDown={(event) => {
          // Avoid browser focus-scroll jumping the whole page under the PDF pane.
          if (event.button === 0) event.preventDefault()
        }}
        onClick={onSelect}
        aria-pressed={selected}
        className="w-full text-left"
      >
        <div className="flex items-start justify-between gap-3">
          <p
            className={
              overridden
                ? 'text-sm font-semibold text-cas-soft line-through'
                : 'text-sm font-semibold text-cas-ink'
            }
          >
            {label}
          </p>
          <div className="flex shrink-0 items-center gap-1.5">
            {overridden ? (
              <span className="rounded bg-cas-border px-1.5 py-0.5 text-[11px] font-semibold text-cas-muted">
                False positive
              </span>
            ) : null}
            {badge ? (
              <span className="rounded bg-mcmaster-gold/70 px-1.5 py-0.5 text-[11px] font-semibold text-cas-ink">
                {badge}
              </span>
            ) : null}
          </div>
        </div>
        <p className="mt-1 text-xs leading-relaxed text-cas-muted">{detail}</p>
      </button>

      <div className="mt-2 flex justify-end">
        {overridden ? (
          <button
            type="button"
            onClick={onClearFalsePositive}
            className="text-[11px] font-semibold text-mcmaster-maroon hover:underline"
          >
            Restore check
          </button>
        ) : (
          <button
            type="button"
            onClick={onMarkFalsePositive}
            className="text-[11px] font-semibold text-cas-muted hover:text-mcmaster-maroon hover:underline"
          >
            Mark as false positive
          </button>
        )}
      </div>
    </div>
  )
}

export default PolicyPage
