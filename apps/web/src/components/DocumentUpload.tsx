import { useRef, useState } from 'react'

interface DocumentUploadProps {
  uploading: boolean
  onUpload: (file: File) => Promise<void>
}

const ACCEPT = '.md,.markdown,.txt,.log,.pdf,.docx,.html,.htm'

export function DocumentUpload({ uploading, onUpload }: DocumentUploadProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)
  const [message, setMessage] = useState<string | null>(null)

  const handleFiles = async (files: FileList | null) => {
    const file = files?.[0]
    if (!file) return
    try {
      await onUpload(file)
      setMessage(`已入库：${file.name}`)
    } catch (err) {
      setMessage((err as Error).message)
    }
  }

  return (
    <div className="upload">
      <div
        className={`upload-drop${dragging ? ' dragging' : ''}`}
        onDragOver={(event) => {
          event.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault()
          setDragging(false)
          void handleFiles(event.dataTransfer.files)
        }}
        onClick={() => inputRef.current?.click()}
      >
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPT}
          hidden
          onChange={(event) => void handleFiles(event.target.files)}
        />
        <strong>{uploading ? '正在解析并入库…' : '拖拽文件到这里，或点击选择'}</strong>
        <span className="muted">支持 md / txt / pdf / docx / html</span>
      </div>
      {message && <p className="muted small">{message}</p>}
    </div>
  )
}
