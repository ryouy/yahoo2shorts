import { ArrowRight, Check, CircleAlert, Clock3, Film, FilePlus2, Newspaper, Trash2 } from 'lucide-react'
import type { ProjectSummary } from '../types'
import StatusBadge from '../components/StatusBadge'

interface Props { projects: ProjectSummary[]; onNew: () => void; onOpen: (id: string) => void; onDelete: (id: string) => void; onOpenUsedArticles: () => void }

export default function Dashboard({ projects, onNew, onOpen, onDelete, onOpenUsedArticles }: Props) {
  const completed = projects.reduce((sum, project) => sum + Number(project.success_count || 0), 0)
  const errors = projects.reduce((sum, project) => sum + Number(project.error_count || 0), 0)
  const inProgress = projects.find(project => !['completed', 'error'].includes(project.status))
  return <>
    <header className="page-head dashboard-head">
      <div><span className="eyebrow">DASHBOARD</span><h1>ダッシュボード</h1></div>
      <div className="inline-actions"><button className="secondary" onClick={onOpenUsedArticles}>使用済み記事一覧</button><button className="primary big" onClick={onNew}><FilePlus2 size={19} /> 新しいShortsを作成</button></div>
    </header>
    {inProgress ? <button className="active-strip" onClick={() => onOpen(inProgress.id)}>
      <span className="continue-icon"><Clock3 size={21} /></span><span><small>進行中</small><b>{inProgress.id}</b></span><span className="continue-action">開く <ArrowRight size={17} /></span>
    </button> : null}
    <section className="metric-grid dashboard-stats">
      <div className="metric"><span className="metric-icon pink"><Film /></span><div><small>プロジェクト</small><b>{projects.length}</b></div></div>
      <div className="metric"><span className="metric-icon blue"><Check /></span><div><small>生成済み動画</small><b>{completed}</b></div></div>
      <div className="metric"><span className="metric-icon yellow"><Newspaper /></span><div><small>処理記事</small><b>{projects.reduce((sum, p) => sum + Number(p.article_total || 0), 0)}</b></div></div>
      <div className="metric"><span className="metric-icon red"><CircleAlert /></span><div><small>要確認</small><b>{errors}</b></div></div>
    </section>
    <section className="section-card">
      <div className="section-title"><div><h2>プロジェクト</h2></div><small>{projects.length}件</small></div>
      {projects.length === 0 ? <div className="empty-inline"><p>プロジェクトはありません。</p><button className="text-button" onClick={onNew}>新しく作成 <ArrowRight size={16} /></button></div> :
        <div className="project-list">{projects.map(project => <div key={project.id} className="project-line">
          <button className="project-row" onClick={() => onOpen(project.id)}>
            <span className="project-date"><b>{new Date(project.created_at).toLocaleDateString('ja-JP', { month: 'short', day: 'numeric' })}</b><small>{new Date(project.created_at).toLocaleTimeString('ja-JP', { hour: '2-digit', minute: '2-digit' })}</small></span>
            <span className="project-info"><b>{project.id}</b><small>{project.article_total || 0}記事 ・ 成功 {project.success_count || 0} ・ 失敗 {project.error_count || 0}</small></span>
            <StatusBadge status={project.status} /><ArrowRight size={18} />
          </button>
          <button className="delete-project dashboard-delete" aria-label={`${project.id}を削除`} onClick={() => { if (confirm(`${project.id} と成果物を削除しますか？`)) onDelete(project.id) }}><Trash2 size={16} /></button>
        </div>)}</div>}
    </section>
  </>
}
