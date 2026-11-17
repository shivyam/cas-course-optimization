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

      <div className="mb-4 flex flex-wrap gap-3">
        <Link
          to="/admin/outline-review"
          className="rounded-lg border border-mcmaster-maroon px-4 py-2 text-sm font-semibold text-mcmaster-maroon hover:bg-mcmaster-maroon hover:text-white"
        >
          Upload more outlines
        </Link>
        <Link
          to="/admin"
          className="rounded-lg border border-cas-border px-4 py-2 text-sm font-semibold text-cas-muted hover:text-cas-ink"
        >
          Administrator dashboard
        </Link>
      </div>

      {outlines.length > 1 && (
        <div className="mb-4 flex flex-wrap gap-2">
          {outlines.map((outline, index) => (
            <button
              key={`${outline.filename}-${index}`}
              type="button"
              onClick={() => setActiveIndex(index)}
              className={`rounded-lg border px-3 py-2 text-left text-sm ${
                index === activeIndex
                  ? 'border-mcmaster-maroon bg-cas-tint font-semibold text-mcmaster-maroon'
                  : 'border-cas-border bg-white text-cas-ink hover:border-mcmaster-maroon'
              }`}
            >
              <span className="block max-w-56 truncate">{outline.filename}</span>
              <span className="text-xs text-cas-muted">
                {(outline.sizeBytes / 1024 / 1024).toFixed(2)} MB
              </span>
            </button>
          ))}
        </div>
      )}

      <div className="rounded-lg border border-cas-border bg-white p-4 shadow-sm sm:p-6">
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
    </section>
  )
}

export default OutlinePreviewPage
