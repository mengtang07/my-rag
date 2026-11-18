import type { Citation } from '../types/api'

interface SourceListProps {
  citations: Citation[]
}

export function SourceList({ citations }: SourceListProps) {
  if (citations.length === 0) return null

  return (
    <div className="sources">
      <span className="sources-label">引用来源</span>
      <ul>
        {citations.map((citation) => (
          <li key={citation.chunk_id}>
            <span className="sources-index">[{citation.index}]</span>
            <span className="sources-title">{citation.document_title}</span>
            {citation.heading_path && (
              <span className="sources-heading"> / {citation.heading_path}</span>
            )}
            {citation.page_number && (
              <span className="sources-heading"> / 第 {citation.page_number} 页</span>
            )}
            <span className="sources-score">score {citation.score.toFixed(3)}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}
