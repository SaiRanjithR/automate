import { Upload } from 'lucide-react'
import { useId, useState, type DragEvent } from 'react'

import { cn } from '@/lib/utils'

type DropzoneProps = {
  label: string
  hint?: string
  multiple?: boolean
  accept?: string
  disabled?: boolean
  onFiles: (files: File[]) => void
}

export function Dropzone({
  label,
  hint = 'PDF or Word (.docx), up to 50 MB',
  multiple = false,
  accept = '.pdf,.docx',
  disabled = false,
  onFiles,
}: DropzoneProps) {
  const id = useId()
  const [dragging, setDragging] = useState(false)

  const onDrop = (event: DragEvent<HTMLLabelElement>) => {
    event.preventDefault()
    setDragging(false)
    if (disabled) return
    const files = Array.from(event.dataTransfer.files)
    if (files.length) onFiles(multiple ? files : files.slice(0, 1))
  }

  return (
    <label
      htmlFor={id}
      onDragOver={(event) => {
        event.preventDefault()
        setDragging(true)
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={onDrop}
      className={cn(
        'flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed border-border px-6 py-8 text-center transition-colors hover:border-primary/60 hover:bg-muted/40',
        dragging && 'border-primary bg-primary/5',
        disabled && 'pointer-events-none opacity-50',
      )}
    >
      <Upload aria-hidden="true" className="size-6 text-muted-foreground" />
      <span className="text-sm font-medium">{label}</span>
      <span className="text-xs text-muted-foreground">{hint}</span>
      <input
        id={id}
        type="file"
        className="sr-only"
        accept={accept}
        multiple={multiple}
        disabled={disabled}
        onChange={(event) => {
          const files = Array.from(event.target.files ?? [])
          if (files.length) onFiles(files)
          event.target.value = ''
        }}
      />
    </label>
  )
}
