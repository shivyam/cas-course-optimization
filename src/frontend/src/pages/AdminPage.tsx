import { useState } from 'react'
import { useNavigate } from 'react-router'
import type { ChangeEvent, DragEvent, FormEvent } from 'react'

// Use the Vite proxy in development, while allowing deployments to provide
// the backend URL through the VITE_API_BASE_URL environment variable.
const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? '/api'

type UploadState = 'idle' | 'uploading' | 'success' | 'error'

function AdminPage() {
  // These states keep the selected file and user feedback synchronized with
  // the upload request lifecycle.
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [uploadState, setUploadState] = useState<UploadState>('idle')
  const [message, setMessage] = useState('')
  const [isDragging, setIsDragging] = useState(false)
  // Router navigation carries the extraction result to the preview page
  // without requiring a second request immediately after uploading.
  const navigate = useNavigate()

  // Centralize file selection so picker, drag-and-drop, and removal all reset
  // stale status messages consistently.
  function selectFile(file: File | null) {
    setSelectedFile(file)
    setUploadState('idle')
    setMessage('')
  }

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    selectFile(event.target.files?.[0] ?? null)
  }

  // Prevent the browser's default file-opening behavior and use the dropped
  // file as the current upload selection instead.
  function handleDrop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault()
    setIsDragging(false)
    selectFile(event.dataTransfer.files[0] ?? null)
  }

  function formatFileSize(bytes: number) {
    return `${(bytes / 1024 / 1024).toFixed(2)} MB`
  }

  // Upload the selected PDF and pass the backend's extracted text to the
  // preview route after a successful response.
  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    if (!selectedFile) {
      setUploadState('error')
      setMessage('Select a PDF course outline before uploading.')
      return
    }

    setUploadState('uploading')
    setMessage('')

    // FormData is required because the API expects multipart/form-data.
    const formData = new FormData()
    formData.append('file', selectedFile)

    try {
      // Send course outline file to backend
      const response = await fetch(`${apiBaseUrl}/outlines`, {
        method: 'POST',
        body: formData,
      })
      // The response contains either extracted text or error message.
      const body = (await response.json()) as {
        detail?: string
        filename?: string
        size_bytes?: number
        text?: string
      }

      if (!response.ok) {
        throw new Error(body.detail ?? 'The course outline could not be uploaded.')
      }

      setUploadState('success')
      setMessage(`${body.filename ?? selectedFile.name} uploaded successfully.`)
      // Keep the extracted text in navigation state so the preview can render
      // it immediately after a successful upload.
      navigate('/admin/outline-preview', {
        state: {
          filename: body.filename ?? selectedFile.name,
          sizeBytes: body.size_bytes ?? selectedFile.size,
          text: body.text ?? '',
        },
      })
    } catch (error) {
      setUploadState('error')
      setMessage(
        error instanceof Error
          ? error.message
          : 'The course outline could not be uploaded.',
      )
    }
  }

  return (
    <section className="mx-auto max-w-4xl space-y-8">
      <header className="space-y-3">
        <p className="text-sm font-semibold uppercase tracking-[0.2em] text-mcmaster-maroon">
          Administration
        </p>
        <h1 className="text-3xl font-bold tracking-tight text-gray-950">Admin</h1>
        <h2 className="text-xl font-semibold text-gray-900">Course outlines</h2>
        <p className="max-w-2xl text-base leading-7 text-mcmaster-grey">
          Add a course outline to prepare it for text extraction and assessment planning.
        </p>
      </header>

      <div className="grid gap-6 lg:grid-cols-[1.4fr_0.8fr]">
        <form
          className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm sm:p-8"
          onSubmit={handleSubmit}
        >
          <div className="mb-6 flex items-start justify-between gap-4">
            <div>
              <h2 className="text-lg font-semibold text-gray-950">Upload a PDF</h2>
              <p className="mt-1 text-sm text-mcmaster-grey">Maximum file size: 10 MB</p>
            </div>
            <span className="rounded-full bg-mcmaster-gold/20 px-3 py-1 text-xs font-bold uppercase tracking-wide text-mcmaster-maroon">
              PDF only
            </span>
          </div>

          {/* The label makes the entire drop zone clickable. */}
          <label
            htmlFor="outline-file"
            onDragEnter={(event) => {
              event.preventDefault()
              setIsDragging(true)
            }}
            onDragOver={(event) => event.preventDefault()}
            onDragLeave={() => setIsDragging(false)}
            onDrop={handleDrop}
            className={`flex min-h-56 cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 text-center transition ${
              isDragging
                ? 'border-mcmaster-maroon bg-mcmaster-maroon/5'
                : 'border-gray-300 bg-gray-50 hover:border-mcmaster-maroon hover:bg-mcmaster-maroon/5'
            }`}
          >
            <span className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-mcmaster-maroon text-2xl text-white">
              +
            </span>
            <span className="font-semibold text-gray-900">Drop your PDF here</span>
            <span className="mt-1 text-sm text-mcmaster-grey">
              or <span className="font-semibold text-mcmaster-maroon">browse files</span>
            </span>
            <input
              id="outline-file"
              name="file"
              type="file"
              accept="application/pdf,.pdf"
              onChange={handleFileChange}
              className="sr-only"
            />
          </label>

          {selectedFile && (
            <div className="mt-4 flex items-center justify-between gap-4 rounded-lg border border-gray-200 bg-gray-50 p-4">
              <div className="flex min-w-0 items-center gap-3">
                <span className="rounded bg-red-100 px-2 py-1 text-xs font-bold text-red-700">
                  PDF
                </span>
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold text-gray-900">
                    {selectedFile.name}
                  </p>
                  <p className="text-xs text-mcmaster-grey">
                    {formatFileSize(selectedFile.size)}
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => selectFile(null)}
                className="shrink-0 text-sm font-semibold text-mcmaster-maroon hover:underline"
              >
                Remove
              </button>
            </div>
          )}

          <div className="mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-xs text-mcmaster-grey">
              Files are validated before they are processed.
            </p>
            <button
              type="submit"
              disabled={uploadState === 'uploading'}
              className="rounded-lg bg-mcmaster-maroon px-5 py-3 font-semibold text-white shadow-sm transition hover:bg-mcmaster-maroon/90 focus:outline-none focus:ring-2 focus:ring-mcmaster-gold focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {uploadState === 'uploading' ? 'Uploading...' : 'Upload outline'}
            </button>
          </div>

          {message && (
            <p
              role="status"
              className={`mt-4 rounded-lg px-4 py-3 text-sm font-medium ${
                uploadState === 'error'
                  ? 'bg-red-50 text-red-700'
                  : 'bg-green-50 text-green-700'
              }`}
            >
              {message}
            </p>
          )}
        </form>

        <aside className="rounded-2xl bg-mcmaster-maroon p-6 text-white shadow-sm sm:p-8">
          <p className="text-sm font-semibold uppercase tracking-[0.15em] text-mcmaster-gold">
            What happens next?
          </p>
          <ol className="mt-6 space-y-6">
            {[
              ['01', 'Upload', 'Add a current course outline as a PDF.'],
              ['02', 'Validate', 'We check the file type and size.'],
              [
                '03',
                'Extract & Compare',
                'The outline will be converted into usable text and compared against university guidelines.',
              ],
            ].map(([number, title, description]) => (
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

export default AdminPage
