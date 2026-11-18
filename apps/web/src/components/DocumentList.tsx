import type { DocumentBrief } from '../types/api'

interface DocumentListProps {
  documents: DocumentBrief[]
  loading: boolean
  onDelete: (id: number) => void
}

const STATUS_LABELS: Record<string, string> = {
  pending: '待处理',
  parsing: '解析中',
  indexing: '建索引中',
  ready: '就绪',
  failed: '失败',
}

export function DocumentList({ documents, loading, onDelete }: DocumentListProps) {
  if (loading) {
    return <p className="muted small">加载中…</p>
  }

  if (documents.length === 0) {
    return <p className="muted small">还没有文档，先上传一份试试。</p>
  }

  return (
    <ul className="doc-list">
      {documents.map((doc) => (
        <li key={doc.id} className="doc-item">
          <div className="doc-main">
            <span className="doc-title" title={doc.filename}>
              {doc.title}
            </span>
            <span className={`badge badge-${doc.status}`}>
              {STATUS_LABELS[doc.status] ?? doc.status}
            </span>
          </div>
          <div className="doc-meta">
            <span>{doc.chunk_count} 个切块</span>
            <button className="link" onClick={() => onDelete(doc.id)}>
              删除
            </button>
          </div>
        </li>
      ))}
    </ul>
  )
}
