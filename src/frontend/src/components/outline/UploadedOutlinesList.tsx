import { useState } from 'react'

export type UploadedOutline = {
  id: string
  filename: string
  sizeBytes: number
}

type UploadedOutlinesListProps = {
  files: UploadedOutline[]
  description: string
  activeId?: string
  onSelect?: (id: string) => void
  onRemove?: (id: string) => void
  showRemove?: boolean
}

function formatFileSize(bytes: number) {
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`
}

function fileType(filename: string) {
  const lowerName = filename.toLowerCase()
  if (lowerName.endsWith('.docx')) return 'DOCX'
  if (lowerName.endsWith('.tex')) return 'TEX'
  return 'PDF'
}

function UploadedOutlinesList({
  files,
  description,
  activeId,
  onSelect,
  onRemove,
  showRemove = false,
}: UploadedOutlinesListProps) {
  const [showAllFiles, setShowAllFiles] = useState(false)
  const visibleFiles = showAllFiles ? files : files.slice(0, 4)

  return (
    <section className="rounded-2xl border border-cas-border bg-white p-5 shadow-sm sm:p-6">
      <h2 className="text-lg font-semibold text-cas-ink">Uploaded course outlines</h2>
      <p className="mt-1 text-sm text-cas-muted">{description}</p>
      {files.length > 0 ? (
        <ul
          className={`mt-4 space-y-2 ${
            showAllFiles ? 'max-h-80 overflow-y-auto pr-1' : ''
          }`}
        >
          {visibleFiles.map((file) => (
            <li
              key={file.id}
              className="flex items-center justify-between gap-4 rounded-lg border border-cas-border bg-cas-surface p-4"
            >
              {onSelect ? (
                <button
                  type="button"
                  onClick={() => onSelect(file.id)}
                  className={`flex min-w-0 flex-1 items-center gap-3 rounded text-left ${
                    file.id === activeId ? 'text-mcmaster-maroon' : 'text-cas-ink'
                  }`}
                >
                  <FileSummary file={file} />
                </button>
              ) : (
                <FileSummary file={file} />
              )}
              {showRemove && onRemove && (
                <button
                  type="button"
                  onClick={() => onRemove(file.id)}
                  className="shrink-0 text-sm font-semibold text-mcmaster-maroon hover:underline"
                >
                  Remove
                </button>
              )}
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-4 text-sm text-cas-muted">No outlines uploaded yet.</p>
      )}
      {files.length > 4 && !showAllFiles && (
        <button
          type="button"
          onClick={() => setShowAllFiles(true)}
          className="mt-4 w-full rounded-lg border border-mcmaster-maroon px-4 py-2.5 text-sm font-semibold text-mcmaster-maroon transition hover:bg-mcmaster-maroon hover:text-white"
        >
          Load all files ({files.length})
        </button>
      )}
    </section>
  )
}

function FileSummary({ file }: { file: UploadedOutline }) {
  return (
    <>
      <span className="rounded bg-red-100 px-2 py-1 text-xs font-bold text-red-700">
        {fileType(file.filename)}
      </span>
      <span className="min-w-0">
        <span className="block truncate text-sm font-semibold">{file.filename}</span>
        <span className="block text-xs text-cas-muted">
          {formatFileSize(file.sizeBytes)}
        </span>
      </span>
    </>
  )
}

export default UploadedOutlinesList
