import { ChatPanel } from './components/ChatPanel'
import { DocumentList } from './components/DocumentList'
import { DocumentUpload } from './components/DocumentUpload'
import { Layout } from './components/Layout'
import { useDocuments } from './hooks/useDocuments'

export default function App() {
  const { documents, loading, uploading, error, refresh, upload, remove } =
    useDocuments()

  return (
    <Layout
      sidebar={
        <>
          <h2>知识库</h2>
          <DocumentUpload uploading={uploading} onUpload={upload} />
          {error && <p className="error">{error}</p>}
          <DocumentList
            documents={documents}
            loading={loading}
            onDelete={(id) => void remove(id)}
          />
          <button className="link" onClick={() => void refresh()}>
            刷新列表
          </button>
        </>
      }
    >
      <ChatPanel />
    </Layout>
  )
}
