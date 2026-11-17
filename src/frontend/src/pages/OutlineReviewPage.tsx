import { useRef, useState } from 'react'
import type { ChangeEvent, DragEvent } from 'react'
import { useNavigate } from 'react-router'
import PageHeader from '../components/layout/PageHeader.tsx'

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? '/api'
const maxBatchFiles = 50
const maxFileSizeBytes = 10 * 1024 * 1024

type UploadState = 'idle' | 'uploading' | 'error' | 'partial'

type BatchResult = {
  ok?: boolean
  filename?: string
  size_bytes?: number
  text?: string
  detail?: string
}

type SelectedPdf = {
  id: string
  file: File
}

function formatFileSize(bytes: number) {
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`
}

function isPdfFile(file: File) {
  return (
    file.type === 'application/pdf' ||
    file.type === 'application/x-pdf' ||
    file.name.toLowerCase().endsWith('.pdf')
  )
}

function OutlineReviewPage() {
  const navigate = useNavigate()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [selectedFiles, setSelectedFiles] = useState<SelectedPdf[]>([])
  const [isDragging, setIsDragging] = useState(false)
  const [uploadState, setUploadState] = useState<UploadState>('idle')
  const [uploadMessage, setUploadMessage] = useState('')

  function addFiles(fileList: FileList | File[]) {
    const incoming = Array.from(fileList)
    const next: SelectedPdf[] = []
    const errors: string[] = []

    for (const file of incoming) {
      if (!isPdfFile(file)) {
        errors.push(`${file.name}: only PDF files are supported.`)
        continue
      }
      if (file.size > maxFileSizeBytes) {
        errors.push(`${file.name}: must be 10 MB or smaller.`)
        continue
      }
      next.push({
        id: `${file.name}-${file.size}-${file.lastModified}-${crypto.randomUUID()}`,
        file,
      })
    }

    setSelectedFiles((current) => {
      const combined = [...current, ...next]
      const deduped = combined.filter(
        (item, index, all) =>
          all.findIndex(
            (other) =>
              other.file.name === item.file.name &&
              other.file.size === item.file.size &&
              other.file.lastModified === item.file.lastModified,
          ) === index,
      )

      if (deduped.length > maxBatchFiles) {
        errors.push(`Upload at most ${maxBatchFiles} PDF files at once.`)
        return deduped.slice(0, maxBatchFiles)
      }
      return deduped
    })

    setUploadState(errors.length ? 'error' : 'idle')
    setUploadMessage(errors.join(' '))
  }

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    if (event.target.files?.length) {
      addFiles(event.target.files)
    }
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  function handleDrop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault()
    setIsDragging(false)
    if (event.dataTransfer.files.length) {
      addFiles(event.dataTransfer.files)
    }
  }

  function removeFile(id: string) {
    setSelectedFiles((current) => current.filter((item) => item.id !== id))
    setUploadState('idle')
    setUploadMessage('')
  }

  async function handleUpload() {
    if (!selectedFiles.length) {
      setUploadState('error')
      setUploadMessage('Select one or more PDF course outlines before uploading.')
      return
    }

    setUploadState('uploading')
    setUploadMessage('')

    const formData = new FormData()
    for (const item of selectedFiles) {
      formData.append('files', item.file)
    }

    try {
      const response = await fetch(`${apiBaseUrl}/outlines/batch`, {
        method: 'POST',
        body: formData,
      })
      const body = (await response.json()) as {
        detail?: string
        results?: BatchResult[]
      }

      if (!response.ok) {
        throw new Error(
          typeof body.detail === 'string'
            ? body.detail
            : 'The course outlines could not be uploaded.',
        )
      }

      const results = body.results ?? []
      const successes = results.filter((result) => result.ok)
      const failures = results.filter((result) => !result.ok)

      if (!successes.length) {
        setUploadState('error')
        setUploadMessage(
          failures
            .map((result) => `${result.filename}: ${result.detail ?? 'failed'}`)
            .join(' ') || 'No PDFs were uploaded successfully.',
        )
        return
      }

      if (failures.length) {
        setUploadState('partial')
        setUploadMessage(
          `Uploaded ${successes.length} of ${results.length}. Failed: ${failures
            .map((result) => `${result.filename} (${result.detail ?? 'error'})`)
            .join('; ')}`,
        )
      }

      navigate('/admin/outline-preview', {
        state: {
          outlines: successes.map((result) => ({
            filename: result.filename ?? 'outline.pdf',
            sizeBytes: result.size_bytes ?? 0,
            text: result.text ?? '',
          })),
          filename: successes[0]?.filename,
          sizeBytes: successes[0]?.size_bytes,
          text: successes[0]?.text ?? '',
        },
      })
    } catch (error) {
      setUploadState('error')
      setUploadMessage(
        error instanceof Error
          ? error.message
          : 'The course outlines could not be uploaded.',
      )
    }
  }

  return (
    <section>
      <PageHeader
        eyebrow="Administration"
        title="Course outline upload & review"
        description="Upload one or more PDF course outlines to extract text for planning review."
      />

      <div className="mb-4 space-y-4 rounded-lg border border-cas-border bg-cas-surface p-4 sm:p-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <p className="text-base font-semibold text-cas-ink">
              {selectedFiles.length
                ? `${selectedFiles.length} PDF${selectedFiles.length === 1 ? '' : 's'} selected`
                : 'No outlines selected'}
            </p>
            <p className="mt-1 text-xs text-cas-muted">
              Max {maxBatchFiles} files · 10 MB each · PDF only
            </p>
          </div>
          <div className="flex flex-col gap-2 sm:flex-row">
            <input
              ref={fileInputRef}
              id="outline-pdfs"
              type="file"
              accept="application/pdf,.pdf"
              multiple
              className="sr-only"
              onChange={handleFileChange}
            />
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={uploadState === 'uploading'}
              className="h-10 rounded-lg border border-cas-border bg-white px-4 text-sm font-semibold text-mcmaster-maroon disabled:opacity-60"
            >
              Browse PDFs
            </button>
            <button
              type="button"
              onClick={handleUpload}
              disabled={uploadState === 'uploading' || !selectedFiles.length}
              className="h-10 rounded-lg bg-mcmaster-maroon px-4 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
            >
              {uploadState === 'uploading'
                ? `Uploading ${selectedFiles.length}…`
                : selectedFiles.length > 1
                  ? `Upload ${selectedFiles.length} outlines`
                  : 'Upload outline'}
            </button>
          </div>
        </div>

        <label
          htmlFor="outline-pdfs"
          onDragEnter={(event) => {
            event.preventDefault()
            setIsDragging(true)
          }}
          onDragOver={(event) => event.preventDefault()}
          onDragLeave={() => setIsDragging(false)}
          onDrop={handleDrop}
          className={`flex min-h-36 cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed px-4 text-center transition ${
            isDragging
              ? 'border-mcmaster-maroon bg-mcmaster-maroon/5'
              : 'border-cas-border bg-white hover:border-mcmaster-maroon'
          }`}
        >
          <span className="font-semibold text-cas-ink">Drop one or many PDFs here</span>
          <span className="mt-1 text-sm text-cas-muted">
            or use Browse PDFs to select multiple files
          </span>
        </label>

        {selectedFiles.length > 0 && (
          <ul className="space-y-2">
            {selectedFiles.map((item) => (
              <li
                key={item.id}
                className="flex items-center justify-between gap-3 rounded-lg border border-cas-border bg-white px-3 py-2"
              >
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold text-cas-ink">
                    {item.file.name}
                  </p>
                  <p className="text-xs text-cas-muted">
                    {formatFileSize(item.file.size)}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => removeFile(item.id)}
                  disabled={uploadState === 'uploading'}
                  className="shrink-0 text-sm font-semibold text-mcmaster-maroon hover:underline disabled:opacity-60"
                >
                  Remove
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {uploadMessage && (
        <p
          role="status"
          className={`mb-4 rounded-lg px-4 py-3 text-sm ${
            uploadState === 'error' || uploadState === 'partial'
              ? 'bg-red-50 text-red-700'
              : 'bg-green-50 text-green-700'
          }`}
        >
          {uploadMessage}
        </p>
      )}

      <div className="grid gap-6 xl:grid-cols-2">
        <article className="rounded-lg border border-cas-border bg-white p-5 sm:p-6">
          <h2 className="text-lg font-semibold text-cas-ink">Extracted assessments</h2>
          <p className="mt-1 text-sm text-cas-muted">
            Assessment rows will appear here after extraction and review are connected.
          </p>
          <div className="mt-6 rounded-lg border border-dashed border-cas-border bg-cas-surface px-4 py-10 text-center text-sm text-cas-muted">
            No extracted assessments yet
          </div>
        </article>

        <aside className="rounded-lg border border-cas-border bg-white p-5 sm:p-6">
          <h2 className="text-lg font-semibold text-cas-ink">Source evidence</h2>
          <p className="mt-1 text-sm text-cas-muted">
            Citation text for a selected assessment will appear here.
          </p>
          <div className="mt-6 rounded-lg border border-dashed border-cas-border bg-cas-surface px-4 py-10 text-center text-sm text-cas-muted">
            No source citation selected
          </div>
        </aside>
      </div>
    </section>
  )
}

export default OutlineReviewPage
