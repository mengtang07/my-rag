import { useCallback, useEffect, useState } from 'react'
import {
  deleteDocument,
  listDocuments,
  uploadDocument,
} from '../api/documents'
import type { DocumentBrief } from '../types/api'

export interface UseDocumentsResult {
  documents: DocumentBrief[]
  loading: boolean
  uploading: boolean
  error: string | null
  refresh: () => Promise<void>
  upload: (file: File) => Promise<void>
  remove: (id: number) => Promise<void>
}

export function useDocuments(): UseDocumentsResult {
  const [documents, setDocuments] = useState<DocumentBrief[]>([])
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    setLoading(true)
    try {
      const page = await listDocuments()
      setDocuments(page.items)
      setError(null)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  const upload = useCallback(
    async (file: File) => {
      setUploading(true)
      try {
        await uploadDocument(file)
        setError(null)
        await refresh()
      } catch (err) {
        setError((err as Error).message)
        throw err
      } finally {
        setUploading(false)
      }
    },
    [refresh],
  )

  const remove = useCallback(
    async (id: number) => {
      try {
        await deleteDocument(id)
        await refresh()
      } catch (err) {
        setError((err as Error).message)
      }
    },
    [refresh],
  )

  return { documents, loading, uploading, error, refresh, upload, remove }
}
