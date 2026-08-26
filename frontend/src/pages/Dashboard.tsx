import { ArrowRight, Check, CircleAlert, Film, FilePlus2, Newspaper } from 'lucide-react'
import type { ProjectSummary } from '../types'
import StatusBadge from '../components/StatusBadge'

interface Props { projects: ProjectSummary[]; onNew: () => void; onOpen: (id: string) => void }

export default function Dashboard({ projects, onNew, onOpen }: Props) {
  const latest = projects.slice(0, 5)
  const completed = projects.reduce((sum, project) => sum + Number(project.success_count || 0), 0)
  const errors = projects.reduce((sum, project) => sum + Number(project.error_count || 0), 0)
  return <>
    <header className="page-head dashboard-head">
      <div><span className="eyebrow">CREATION DESK</span><h1>ダッシュボード</h1><p>ニュース選びから縦型動画まで、ひとつの制作フローで。</p></div>
      <button className="primary big" onClick={onNew}><FilePlus2 size={19} /> 新しいShortsを作成</button>
    </header>
    <section className="metric-grid">
      <div className="metric"><span className="metric-icon pink"><Film /></span><div><small>プロジェクト</small><b>{projects.length}</b></div></div>
      <div className="metric"><span className="metric-icon blue"><Check /></span><div><small>生成済み動画</small><b>{completed}</b></div></div>
      <div className="metric"><span className="metric-icon yellow"><Newspaper /></span><div><small>処理記事</small><b>{projects.reduce((sum, p) => sum + Number(p.article_total || 0), 0)}</b></div></div>
      <div className="metric"><span className="metric-icon red"><CircleAlert /></span><div><small>要確認</small><b>{errors}</b></div></div>
    </section>
    <section className="section-card">
      <div className="section-title"><div><h2>最近のプロジェクト</h2><p>途中の作業もそのまま再開できます</p></div></div>
      {latest.length === 0 ? <div className="empty-inline"><p>まだプロジェクトがありません。</p><button className="text-button" onClick={onNew}>最初の1本を作る <ArrowRight size={16} /></button></div> :
        <div className="project-list">{latest.map(project => <button key={project.id} className="project-row" onClick={() => onOpen(project.id)}>
          <span className="project-date"><b>{new Date(project.created_at).toLocaleDateString('ja-JP', { month: 'short', day: 'numeric' })}</b><small>{new Date(project.created_at).toLocaleTimeString('ja-JP', { hour: '2-digit', minute: '2-digit' })}</small></span>
          <span className="project-info"><b>{project.id}</b><small>{project.article_total || 0}記事 ・ 成功 {project.success_count || 0} ・ 失敗 {project.error_count || 0}</small></span>
          <StatusBadge status={project.status} /><ArrowRight size={18} />
        </button>)}</div>}
    </section>
  </>
}

