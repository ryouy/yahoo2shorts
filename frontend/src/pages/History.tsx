import { ArrowRight, CalendarDays, Film, Search } from 'lucide-react'
import { useMemo, useState } from 'react'
import StatusBadge from '../components/StatusBadge'
import type { ProjectSummary } from '../types'

export default function History({ projects, onOpen }: { projects: ProjectSummary[]; onOpen: (id: string) => void }) {
  const [query, setQuery] = useState('')
  const filtered = useMemo(() => projects.filter(project => project.id.includes(query.trim())), [projects, query])
  return <>
    <header className="page-head"><div><span className="eyebrow">ARCHIVE</span><h1>プロジェクト履歴</h1><p>PCを再起動しても、途中の状態から作業を再開できます。</p></div></header>
    <section className="section-card">
      <div className="history-toolbar"><div className="search-box"><Search size={17} /><input value={query} onChange={e => setQuery(e.target.value)} placeholder="Project IDで検索" /></div><span>{filtered.length} projects</span></div>
      <div className="history-grid">{filtered.map(project => <button className="history-card" key={project.id} onClick={() => onOpen(project.id)}>
        <div className="history-top"><span className="calendar"><CalendarDays /></span><StatusBadge status={project.status} /></div>
        <h3>{project.id}</h3><p>{new Date(project.created_at).toLocaleString('ja-JP')}</p>
        <div className="history-stats"><span><Film size={16} /> {project.article_total || 0} 記事</span><span>成功 <b>{project.success_count || 0}</b></span><span>失敗 <b>{project.error_count || 0}</b></span></div>
        <span className="open-link">開く <ArrowRight size={16} /></span>
      </button>)}</div>
      {!filtered.length && <div className="empty-inline">該当するプロジェクトはありません。</div>}
    </section>
  </>
}

