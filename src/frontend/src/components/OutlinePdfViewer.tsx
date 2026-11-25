import { useEffect, useRef, useState } from 'react'
import { getDocument, GlobalWorkerOptions } from 'pdfjs-dist'
import type { PDFDocumentProxy } from 'pdfjs-dist'
import pdfWorker from 'pdfjs-dist/build/pdf.worker.min.mjs?url'

GlobalWorkerOptions.workerSrc = pdfWorker

export type PdfHighlight = {
  x0: number
  y0: number
  x1: number
  y1: number
}

type OutlinePdfViewerProps = {
  url: string
  page: number
  highlights: PdfHighlight[]
  focusLabel?: string
  pageWidth?: number
  pageHeight?: number
}

function OutlinePdfViewer({
  url,
  page,
  highlights,
  focusLabel,
  pageWidth = 612,
  pageHeight = 792,
}: OutlinePdfViewerProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const scrollRef = useRef<HTMLDivElement | null>(null)
  const focusRef = useRef<HTMLDivElement | null>(null)
  const [pdf, setPdf] = useState<PDFDocumentProxy | null>(null)
  const [renderWidth, setRenderWidth] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    let loaded: PDFDocumentProxy | null = null
    setLoading(true)
    setError(null)
    setPdf(null)

    getDocument(url)
      .promise.then((document) => {
        if (cancelled) {
          void document.destroy()
          return
        }
        loaded = document
        setPdf(document)
      })
      .catch(() => {
        if (!cancelled) setError('Could not load the course outline PDF.')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
      if (loaded) void loaded.destroy()
    }
  }, [url])

  useEffect(() => {
    const container = scrollRef.current
    if (!container) return

    const updateWidth = () => {
      setRenderWidth(Math.max(280, container.clientWidth - 24 || 480))
    }
    updateWidth()

    if (typeof ResizeObserver === 'undefined') return

    const observer = new ResizeObserver(updateWidth)
    observer.observe(container)
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    if (!pdf || !canvasRef.current || renderWidth <= 0) return

    let cancelled = false
    const canvas = canvasRef.current
    const targetPage = Math.min(Math.max(page, 1), pdf.numPages)

    void pdf.getPage(targetPage).then((pdfPage) => {
      if (cancelled) return

      const viewport = pdfPage.getViewport({ scale: 1 })
      const scale = renderWidth / viewport.width
      const scaled = pdfPage.getViewport({ scale })
      const context = canvas.getContext('2d')
      if (!context) return

      canvas.width = scaled.width
      canvas.height = scaled.height
      canvas.style.width = `${scaled.width}px`
      canvas.style.height = `${scaled.height}px`

      return pdfPage.render({ canvas, canvasContext: context, viewport: scaled }).promise
    })

    return () => {
      cancelled = true
    }
  }, [pdf, page, renderWidth])

  useEffect(() => {
    const container = scrollRef.current
    const target = focusRef.current
    if (!container || !target) return

    // Scroll only inside the PDF pane — never move the page behind it.
    const containerRect = container.getBoundingClientRect()
    const targetRect = target.getBoundingClientRect()
    const delta =
      targetRect.top -
      containerRect.top -
      container.clientHeight / 2 +
      targetRect.height / 2

    container.scrollTo({
      top: Math.max(0, container.scrollTop + delta),
      behavior: 'smooth',
    })
  }, [page, highlights, renderWidth])

  const scale = renderWidth > 0 ? renderWidth / pageWidth : 1

  return (
    <div className="flex h-full min-h-[28rem] flex-col overflow-hidden rounded-lg border border-cas-border bg-cas-surface">
      <div className="flex items-center justify-between gap-3 border-b border-cas-border bg-white px-3 py-2">
        <p className="text-xs font-semibold text-cas-ink">
          Page {page}
          {focusLabel ? (
            <span className="font-normal text-cas-muted"> · {focusLabel}</span>
          ) : null}
        </p>
        {loading ? <p className="text-xs text-cas-muted">Loading PDF…</p> : null}
      </div>

      <div ref={scrollRef} className="relative flex-1 overflow-auto p-3">
        {error ? (
          <p className="text-sm text-red-700">{error}</p>
        ) : (
          <div
            className="relative mx-auto"
            style={{
              width: renderWidth || pageWidth,
              height: renderWidth ? (renderWidth * pageHeight) / pageWidth : pageHeight,
            }}
          >
            <canvas ref={canvasRef} className="block rounded shadow-sm" />
            {highlights.map((box, index) => {
              const isFocus = index === 0
              const padX = 4
              const padY = 2
              return (
                <div
                  key={`${box.x0}-${box.y0}-${index}`}
                  ref={isFocus ? focusRef : undefined}
                  className={
                    isFocus
                      ? 'pointer-events-none absolute rounded-sm bg-mcmaster-gold/55 ring-2 ring-mcmaster-maroon ring-offset-1'
                      : 'pointer-events-none absolute rounded-sm bg-mcmaster-gold/35'
                  }
                  style={{
                    left: box.x0 * scale - padX,
                    top: box.y0 * scale - padY,
                    width: Math.max((box.x1 - box.x0) * scale + padX * 2, 14),
                    height: (box.y1 - box.y0) * scale + padY * 2,
                  }}
                />
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}

export default OutlinePdfViewer
