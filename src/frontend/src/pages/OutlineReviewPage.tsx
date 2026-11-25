import { useRef, useState } from 'react'
import type { ChangeEvent, DragEvent, FormEvent } from 'react'
import { useNavigate } from 'react-router'
import UploadedOutlinesList from '../components/outline/UploadedOutlinesList.tsx'
import OutlineWorkflowStepper from '../components/outline/OutlineWorkflowStepper.tsx'

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? '/api'
const maxBatchFiles = 50
const maxFileSizeBytes = 10 * 1024 * 1024
const workflowDetails = [
  ['01', 'Course outline upload', 'Add a PDF, LaTeX, or Word course outline.'],
  ['02', 'Text extraction', 'Convert the uploaded outline into readable text.'],
  [
    '03',
    'Review & approve',
    'Check source evidence, correct values and approve the extraction.',
  ],
  [
    '04',
    'Check policy & CEAB',
    'Review policy warnings and verify accreditation mappings.',
  ],
  ['05', 'Plan together', 'See cohort conflicts in the calendar, then review date'],
] as const
type UploadState = 'idle' | 'uploading' | 'error' | 'partial'

type BatchResult = {
  ok?: boolean
  filename?: string
  size_bytes?: number
  text?: string
  detail?: string
}

type SelectedOutline = {
  id: string
  file: File
}

function isSupportedFile(file: File) {
  return (
    file.type === 'application/pdf' ||
    file.type === 'application/x-pdf' ||
    file.type === 'text/x-tex' ||
    file.type === 'application/x-tex' ||
    file.type ===
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document' ||
    ['.pdf', '.tex', '.docx'].some((extension) =>
      file.name.toLowerCase().endsWith(extension),
    )
  )
}

function OutlineReviewPage() {
  const navigate = useNavigate()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [selectedFiles, setSelectedFiles] = useState<SelectedOutline[]>([])
  const [isDragging, setIsDragging] = useState(false)
  const [uploadState, setUploadState] = useState<UploadState>('idle')
  const [uploadMessage, setUploadMessage] = useState('')

  function addFiles(fileList: FileList | File[]) {
    const incoming = Array.from(fileList)
    const next: SelectedOutline[] = []
    const errors: string[] = []

    for (const file of incoming) {
      if (!isSupportedFile(file)) {
        errors.push(`${file.name}: only PDF, LaTeX, or Word files are supported.`)
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
        errors.push(`Upload at most ${maxBatchFiles} outline files at once.`)
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
      setUploadMessage('Select one or more course outline files before uploading.')
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
            .join(' ') || 'No course outlines were uploaded successfully.',
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

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    void handleUpload()
  }

  return (
    <section className="mx-auto max-w-6xl space-y-4">
      <header className="space-y-2">
        <p className="text-sm font-semibold uppercase tracking-[0.2em] text-mcmaster-maroon">
          Administration
        </p>
        <h1 className="text-3xl font-bold tracking-tight text-cas-ink">
          Course outlines
        </h1>
        <p className="max-w-2xl text-base leading-7 text-cas-muted">
          Add course outlines to prepare them for text extraction and assessment planning.
        </p>
      </header>

      <OutlineWorkflowStepper currentStep={0} />

      <div className="grid gap-6 lg:grid-cols-[1.6fr_0.95fr]">
        <div className="min-w-0 space-y-4">
          <form
            className="rounded-2xl border border-cas-border bg-white p-6 shadow-sm sm:p-8"
            onSubmit={handleSubmit}
          >
            <div className="mb-6 flex items-start justify-between gap-4">
              <div>
                <h2 className="text-lg font-semibold text-cas-ink">
                  Upload course outlines
                </h2>
                <p className="mt-1 text-sm text-cas-muted">
                  Maximum {maxBatchFiles} files, 10 MB each
                </p>
              </div>
              <span className="rounded-full bg-mcmaster-gold/20 px-3 py-1 text-xs font-bold uppercase tracking-wide text-mcmaster-maroon">
                PDF · LaTeX · Word
              </span>
            </div>

            <input
              ref={fileInputRef}
              id="outline-files"
              type="file"
              accept="application/pdf,.pdf,text/x-tex,.tex,application/vnd.openxmlformats-officedocument.wordprocessingml.document,.docx"
              multiple
              className="sr-only"
              onChange={handleFileChange}
            />
            <label
              htmlFor="outline-files"
              onDragEnter={(event) => {
                event.preventDefault()
                setIsDragging(true)
              }}
              onDragOver={(event) => event.preventDefault()}
              onDragLeave={() => setIsDragging(false)}
              onDrop={handleDrop}
              className={`flex min-h-48 cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 text-center transition ${
                isDragging
                  ? 'border-mcmaster-maroon bg-mcmaster-maroon/5'
                  : 'border-cas-border bg-cas-surface hover:border-mcmaster-maroon hover:bg-mcmaster-maroon/5'
              }`}
            >
              <span className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-mcmaster-maroon text-2xl text-white">
                +
              </span>
              <span className="font-semibold text-cas-ink">
                Drop your course outlines here
              </span>
              <span className="mt-1 text-sm text-cas-muted">
                or{' '}
                <span className="font-semibold text-mcmaster-maroon">browse files</span>
              </span>
            </label>

            <div className="mt-6 flex w-full items-center justify-center">
              <button
                type="submit"
                disabled={uploadState === 'uploading'}
                className="rounded-lg bg-mcmaster-maroon px-5 py-3 font-semibold text-white shadow-sm transition hover:bg-mcmaster-maroon/90 focus:outline-none focus:ring-2 focus:ring-mcmaster-gold focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {uploadState === 'uploading' ? 'Uploading…' : 'Next →'}
              </button>
            </div>

            {uploadMessage && (
              <p
                role="status"
                className={`mt-4 rounded-lg px-4 py-3 text-sm font-medium ${
                  uploadState === 'error' || uploadState === 'partial'
                    ? 'bg-red-50 text-red-700'
                    : 'bg-green-50 text-green-700'
                }`}
              >
                {uploadMessage}
              </p>
            )}
          </form>

          {selectedFiles.length > 0 && (
            <UploadedOutlinesList
              files={selectedFiles.map((item) => ({
                id: item.id,
                filename: item.file.name,
                sizeBytes: item.file.size,
              }))}
              description="Review or remove files before uploading them for extraction."
              showRemove
              onRemove={removeFile}
            />
          )}
        </div>

        <aside className="rounded-2xl bg-mcmaster-maroon p-6 text-white shadow-sm sm:p-8 lg:self-start lg:h-fit">
          <p className="text-sm font-semibold uppercase tracking-[0.15em] text-mcmaster-gold">
            What happens next?
          </p>
          <ol className="mt-6 space-y-6">
            {workflowDetails.map(([number, title, description]) => (
              <li key={number} className="flex gap-3">
                <span className="text-sm font-bold text-mcmaster-gold">{number}</span>
                <div>
                  <h3 className="font-semibold">{title}</h3>
                  <p className="mt-1 text-sm leading-6 text-white/75">{description}</p>
                </div>
              </li>
            ))}
          </ol>
        </aside>
      </div>
    </section>
  )
}

export default OutlineReviewPage
