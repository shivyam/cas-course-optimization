import { useState } from 'react'
import { Link, useLocation } from 'react-router'
import PageHeader from '../components/layout/PageHeader.tsx'

type OutlinePreviewItem = {
  filename: string
  sizeBytes: number
  text: string
}

type OutlinePreviewState = {
  filename?: string
  sizeBytes?: number
  text?: string
  outlines?: OutlinePreviewItem[]
}

function OutlinePreviewPage() {
  const location = useLocation()
  // Upload results are passed through router state; direct visits intentionally
  // render a safe empty state instead of attempting to read missing data.
  const state = (location.state as OutlinePreviewState | null) ?? null

  const outlines: OutlinePreviewItem[] =
    state?.outlines ??
    (state?.filename
      ? [
          {
            filename: state.filename,
            sizeBytes: state.sizeBytes ?? 0,
            text: state.text ?? '',
          },
        ]
      : [])

  const [activeIndex, setActiveIndex] = useState(0)
  const active = outlines[activeIndex] ?? null
  const text = active?.text ?? ''

  return (
    <section>
      <PageHeader
        eyebrow="Extracted outline"
        title={
          outlines.length > 1
            ? `${outlines.length} course outlines uploaded`
            : (active?.filename ?? 'Course outline text')
        }
        description={
          outlines.length > 1
            ? 'Select an outline below to review its extracted text.'
            : active?.sizeBytes
              ? `${(active.sizeBytes / 1024 / 1024).toFixed(2)} MB extracted from the uploaded PDF.`
              : 'Upload an outline to view its extracted text.'
        }
      />

      <div className="grid gap-6 lg:grid-cols-[280px_minmax(0,1fr)] lg:items-start">
        <aside className="rounded-lg border border-cas-border bg-white p-4 shadow-sm sm:p-5">
          <h2 className="text-sm font-semibold text-cas-ink">Uploaded outlines</h2>
          <p className="mt-1 text-xs leading-5 text-cas-muted">
            Select an outline to review its extracted text.
          </p>
          <div className="mt-4 space-y-2">
            {outlines.map((outline, index) => (
              <button
                key={`${outline.filename}-${index}`}
                type="button"
                onClick={() => setActiveIndex(index)}
                className={`w-full rounded-lg border px-3 py-2.5 text-left text-sm transition ${
                  index === activeIndex
                    ? 'border-mcmaster-maroon bg-cas-tint font-semibold text-mcmaster-maroon'
                    : 'border-cas-border bg-white text-cas-ink hover:border-mcmaster-maroon'
                }`}
              >
                <span className="block truncate">{outline.filename}</span>
                <span className="mt-1 block text-xs text-cas-muted">
                  {(outline.sizeBytes / 1024 / 1024).toFixed(2)} MB
                </span>
              </button>
            ))}
            {!outlines.length && (
              <p className="text-sm text-cas-muted">No outlines uploaded yet.</p>
            )}
          </div>
        </aside>

        <div className="min-w-0 rounded-lg border border-cas-border bg-white p-4 shadow-sm sm:p-6">
          <div className="mb-4 flex items-center justify-between border-b border-cas-border pb-4">
            <div>
              <h2 className="font-semibold text-cas-ink">
                {active?.filename ?? 'Full extracted text'}
              </h2>
              <p className="mt-1 text-sm text-cas-muted">
                Review the content before using it for course planning.
              </p>
            </div>
            <span className="hidden rounded-full bg-green-50 px-3 py-1 text-xs font-semibold text-green-700 sm:inline-flex">
              Extraction complete
            </span>
          </div>
          <pre className="h-[min(65vh,680px)] overflow-y-auto whitespace-pre-wrap rounded-xl bg-cas-surface p-5 text-sm leading-7 text-cas-ink">
            {text || 'No text was found in this PDF.'}
          </pre>
        </div>
      </div>
    </section>
  )
}

export default OutlinePreviewPage
