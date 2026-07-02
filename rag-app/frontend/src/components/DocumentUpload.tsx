import { useCallback, useRef, useState } from 'react'

interface DocumentUploadProps {
  disabled?: boolean
  onUpload: (file: File) => Promise<void>
}

const allowedTypes = '.pdf,.txt,.docx,.csv,.md'

export function DocumentUpload({ disabled, onUpload }: DocumentUploadProps) {
  const inputRef = useRef<HTMLInputElement | null>(null)
  const [isDragging, setIsDragging] = useState(false)

  const handleFile = useCallback(
    async (file?: File) => {
      if (!file || disabled) return
      await onUpload(file)
      if (inputRef.current) inputRef.current.value = ''
    },
    [disabled, onUpload],
  )

  return (
    <div
      className={`upload-zone ${isDragging ? 'upload-zone-active' : ''} ${disabled ? 'opacity-60' : ''}`}
      onDragOver={(event) => {
        event.preventDefault()
        setIsDragging(true)
      }}
      onDragLeave={() => setIsDragging(false)}
      onDrop={(event) => {
        event.preventDefault()
        setIsDragging(false)
        void handleFile(event.dataTransfer.files[0])
      }}
      onClick={() => inputRef.current?.click()}
      role="button"
      tabIndex={0}
    >
      <input
        ref={inputRef}
        className="hidden"
        type="file"
        accept={allowedTypes}
        disabled={disabled}
        onChange={(event) => void handleFile(event.target.files?.[0])}
      />
      <div className="mx-auto mb-3 flex h-10 w-10 items-center justify-center rounded border border-white/15 bg-white/5 text-sm font-semibold text-accent-400">
        UP
      </div>
      <p className="text-sm font-semibold text-slate-100">Upload document</p>
      <p className="mt-1 text-xs leading-5 text-slate-400">PDF, TXT, DOCX, CSV, or MD</p>
    </div>
  )
}
