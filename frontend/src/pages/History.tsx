import { ArrowRight, CalendarDays, Film, Trash2 } from 'lucide-react'
import StatusBadge from '../components/StatusBadge'
import type { ProjectSummary } from '../types'

export default function History({ projects, onOpen, onDelete }: { projects: ProjectSummary[]; onOpen: (id: string) => void; onDelete: (id: string) => void }) {
  return <>
    <header className="page-head compact-head"><div><span className="eyebrow">PROJECTS</span><h1>プロジェクト</h1></div></header>
    <section className="section-card">
      <div className="history-toolbar"><span>{projects.length}件</span></div>
      <div className="history-grid">{projects.map(project => <article className="history-item" key={project.id}>
        <button className="history-card" onClick={() => onOpen(project.id)}>
          <div className="history-top"><span className="calendar"><CalendarDays /></span><StatusBadge status={project.status} /></div>
          <h3>{project.id}</h3><p>{new Date(project.created_at).toLocaleString('ja-JP')}</p>
          <div className="history-stats"><span><Film size={16} /> {project.article_total || 0} 記事</span><span>成功 <b>{project.success_count || 0}</b></span><span>失敗 <b>{project.error_count || 0}</b></span></div>
          <span className="open-link">開く <ArrowRight size={16} /></span>
        </button>
        <button className="delete-project" aria-label={`${project.id}を削除`} onClick={() => { if (confirm(`${project.id} と成果物を削除しますか？`)) onDelete(project.id) }}><Trash2 size={16} /></button>
      </article>)}</div>
      {!projects.length && <div className="empty-inline">プロジェクトはありません。</div>}
    </section>
  </>
}
