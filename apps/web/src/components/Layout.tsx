import type { ReactNode } from 'react'

interface LayoutProps {
  sidebar: ReactNode
  children: ReactNode
}

export function Layout({ sidebar, children }: LayoutProps) {
  return (
    <div className="layout">
      <header className="topbar">
        <span className="brand">my-rag</span>
        <span className="muted small">个人知识库 · RAG</span>
      </header>
      <div className="columns">
        <aside className="sidebar">{sidebar}</aside>
        <main className="content">{children}</main>
      </div>
    </div>
  )
}
