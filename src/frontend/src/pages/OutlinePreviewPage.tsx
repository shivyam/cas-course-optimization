import { Link, useLocation } from 'react-router'

type OutlinePreviewState = {
  filename?: string
  sizeBytes?: number
  text?: string
}

function OutlinePreviewPage() {
  const location = useLocation()
  // Upload results are passed through router state; direct visits intentionally
  // render a safe empty state instead of attempting to read missing data.
  const state = (location.state as OutlinePreviewState | null) ?? null
  const text = state?.text ?? ''

  return (
    <section className="mx-auto max-w-5xl space-y-8">
      <header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div className="space-y-3">
          <p className="text-sm font-semibold uppercase tracking-[0.2em] text-mcmaster-maroon">
            Extracted outline
          </p>
          <h1 className="text-3xl font-bold tracking-tight text-gray-950">
            {state?.filename ?? 'Course outline text'}
          </h1>
          <p className="text-mcmaster-grey">
            {state?.sizeBytes
              ? `${(state.sizeBytes / 1024 / 1024).toFixed(2)} MB`
              : 'Upload an outline to view its extracted text.'}
          </p>
        </div>
        <Link
          to="/admin"
          className="w-fit rounded-lg border border-mcmaster-maroon px-4 py-2 text-sm font-semibold text-mcmaster-maroon hover:bg-mcmaster-maroon hover:text-white"
        >
          Upload another outline
        </Link>
      </header>

      <div className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm sm:p-6">
        <div className="mb-4 flex items-center justify-between border-b border-gray-100 pb-4">
          <div>
            <h2 className="font-semibold text-gray-950">Full extracted text</h2>
            <p className="mt-1 text-sm text-mcmaster-grey">
              Review the content before using it for course planning.
            </p>
          </div>
          <span className="hidden rounded-full bg-green-50 px-3 py-1 text-xs font-semibold text-green-700 sm:inline-flex">
            Extraction complete
          </span>
        </div>
        {/* A bounded, scrollable container prevents long outlines from expanding the page indefinitely. */}
        <pre className="h-[min(65vh,680px)] overflow-y-auto whitespace-pre-wrap rounded-xl bg-gray-50 p-5 text-sm leading-7 text-gray-800">
          {text || 'No text was found in this PDF.'}
        </pre>
      </div>
    </section>
  )
}

export default OutlinePreviewPage
