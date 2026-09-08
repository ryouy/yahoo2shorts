import { ArrowLeft, Check, ChevronRight, Download, FolderOpen, Play, RefreshCw, Sparkles, Video } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import ArticleCard from '../components/ArticleCard'
import EmptyState from '../components/EmptyState'
import ProgressPanel from '../components/ProgressPanel'
import ScriptEditor from '../components/ScriptEditor'
import StatusBadge from '../components/StatusBadge'
import type { Article, Job, Project } from '../types'

type Stage = 'articles' | 'scripts' | 'videos'
interface Props { projectId: string; initialJob?: Job | null; onBack: () => void; onError: (value: string) => void; onNotice: (value: string) => void }

export default function ProjectWorkspace({ projectId, initialJob, onBack, onError, onNotice }: Props) {
  const [project, setProject] = useState<Project | null>(null)
  const [job, setJob] = useState<Job | null>(initialJob || null)
  const [stage, setStage] = useState<Stage>('articles')
  const [selected, setSelected] = useState<number[]>([])
  const [activeArticle, setActiveArticle] = useState<number | null>(null)

  const load = async () => {
    try {
      const value = await api.get<Project>(`/projects/${projectId}`)
      setProject(value)
      setSelected(value.articles.filter(a => a.selected).map(a => a.id))
      const draft = value.articles.find(a => a.script)
      if (!activeArticle && draft) setActiveArticle(draft.id)
      const active = value.jobs.find(candidate => candidate.status === 'running' || candidate.status === 'queued')
      setJob(active || value.jobs[0] || null)
      if (value.articles.some(article => article.video_path || ['generating_video', 'completed'].includes(article.status)) || ['completed', 'partial_error', 'generating_video'].includes(value.status)) setStage('videos')
      else if (value.articles.some(article => article.script) || value.status === 'waiting_script_approval' || value.status === 'ready_for_video') setStage('scripts')
    } catch (e) { onError(e instanceof Error ? e.message : String(e)) }
  }
  useEffect(() => { load() }, [projectId])
  useEffect(() => {
    if (!job || ['completed', 'error'].includes(job.status)) return
    const timer = window.setInterval(async () => {
      try {
        const value = await api.get<Job>(`/jobs/${job.id}`); setJob(value)
        if (value.status === 'completed' || value.status === 'error') await load()
      } catch { /* transient poll failure */ }
    }, 1400)
    return () => clearInterval(timer)
  }, [job?.id, job?.status])

  const articles = project?.articles || []
  const scripted = articles.filter(article => article.script)
  const active = scripted.find(article => article.id === activeArticle) || scripted[0]
  const currentJob = job && (job.status === 'running' || job.status === 'queued') ? job : null
  const visibleJob = currentJob || (job?.status === 'error' ? job : null)
  const completedVideos = articles.filter(article => article.video_path)
  const failedScripts = articles.filter(article => article.selected && article.status === 'error' && !article.script)

  const approveArticles = async () => {
    try {
      await api.post(`/projects/${projectId}/approve-articles`, { article_ids: selected })
      const newJob = await api.post<Job>(`/projects/${projectId}/generate-scripts`)
      setJob(newJob); setStage('scripts'); onNotice(`${selected.length}記事の処理を開始しました。`)
    } catch (e) { onError(e instanceof Error ? e.message : String(e)) }
  }
  const startVideo = async (article: Article) => {
    try { const next = await api.post<Job>(`/articles/${article.id}/generate-video`); setJob(next); setStage('videos') } catch (e) { onError(e instanceof Error ? e.message : String(e)) }
  }
  const retryArticle = async (article: Article) => {
    try { const next = await api.post<Job>(`/articles/${article.id}/retry`); setJob(next); onNotice('この記事だけ再試行します。') } catch (e) { onError(e instanceof Error ? e.message : String(e)) }
  }
  const startVideoBatch = async () => {
    try { const next = await api.post<Job>(`/projects/${projectId}/generate-videos`); setJob(next); setStage('videos'); onNotice('承認済み動画の一括生成を開始しました。') } catch (e) { onError(e instanceof Error ? e.message : String(e)) }
  }
  const openFolder = async () => { try { await api.post(`/projects/${projectId}/open-folder`) } catch (e) { onError(e instanceof Error ? e.message : String(e)) } }

  if (!project) return <div className="loading">プロジェクトを読み込み中…</div>
  return <>
    <header className="workspace-head"><button className="back-button" onClick={onBack}><ArrowLeft size={17} /> 履歴へ</button><div><span>PROJECT</span><h1>{project.id}</h1></div><StatusBadge status={project.status} /></header>
    <div className="workflow-tabs">
      <button className={stage === 'articles' ? 'active' : ''} onClick={() => setStage('articles')}><span>1</span><div><b>記事選択</b><small>候補を承認</small></div></button><ChevronRight />
      <button className={stage === 'scripts' ? 'active' : ''} disabled={!scripted.length && !currentJob} onClick={() => setStage('scripts')}><span>2</span><div><b>原稿編集</b><small>確認と承認</small></div></button><ChevronRight />
      <button className={stage === 'videos' ? 'active' : ''} disabled={!articles.some(a => ['ready_for_video', 'generating_video', 'completed'].includes(a.status)) && !completedVideos.length} onClick={() => setStage('videos')}><span>3</span><div><b>動画生成</b><small>生成とレビュー</small></div></button>
    </div>
    {visibleJob && <ProgressPanel job={visibleJob} />}
    {project.error && <div className="error-banner">{project.error}</div>}

    {stage === 'articles' && <section>
      <div className="stage-title"><div><span className="eyebrow">ARTICLE CANDIDATES</span><h2>記事候補</h2></div><span className="selection-count"><b>{selected.length}</b>件選択中</span></div>
      {articles.length ? <div className="article-list">{articles.map(article => <ArticleCard key={article.id} article={article} checked={selected.includes(article.id)} onToggle={() => setSelected(selected.includes(article.id) ? selected.filter(id => id !== article.id) : [...selected, article.id])} />)}</div> :
        <EmptyState icon={<Sparkles />} title={currentJob ? '記事を探しています' : '候補がありません'} />}
      {!!articles.length && <div className="sticky-action"><span><Check size={18} /> {selected.length}件の記事を選択</span><button className="primary big" disabled={!selected.length || !!currentJob} onClick={approveArticles}>この{selected.length}記事で進む <ChevronRight size={18} /></button></div>}
    </section>}

    {stage === 'scripts' && <section>
      <div className="stage-title"><div><span className="eyebrow">SCRIPT WORKBENCH</span><h2>原稿編集</h2></div></div>
      {scripted.length ? <div className="editor-layout"><aside className="article-tabs">{scripted.map((article, index) => <button className={active?.id === article.id ? 'active' : ''} key={article.id} onClick={() => setActiveArticle(article.id)}><span>{String(index + 1).padStart(2, '0')}</span><div><b>{article.title}</b><small>{article.script?.approved ? '承認済み' : '編集待ち'} ・ {article.script?.estimated_seconds}s</small></div></button>)}</aside>
        <div className="editor-main">{active && <><div className="article-editor-head"><div><small>{active.source}</small><h2>{active.title}</h2></div><StatusBadge status={active.status} /></div>{active.error && <div className="retained-warning">{active.error}</div>}<ScriptEditor article={active} onChanged={load} onError={onError} onNotice={onNotice} /></>}</div></div> :
        <EmptyState icon={<RefreshCw className={currentJob ? 'spin' : ''} />} title={currentJob ? '原稿を生成しています' : '原稿がありません'} />}
      {failedScripts.map(article => <div className="retry-row" key={article.id}><div><b>{article.title || article.url}</b><small>{article.error}</small></div><button className="secondary" disabled={!!currentJob} onClick={() => retryArticle(article)}><RefreshCw size={16} /> この記事だけ再試行</button></div>)}
      {scripted.some(a => a.script?.approved) && <div className="ready-strip"><div><Check /><span><b>承認済み原稿があります</b><small>動画生成へ進めます</small></span></div><button className="primary" onClick={() => setStage('videos')}>動画生成へ <ChevronRight size={17} /></button></div>}
    </section>}

    {stage === 'videos' && <section>
      <div className="stage-title"><div><span className="eyebrow">RENDER & REVIEW</span><h2>動画生成</h2></div><div className="inline-actions"><button className="primary" disabled={!!currentJob || !articles.some(article => article.script?.approved)} onClick={startVideoBatch}><Play size={17} /> 承認済みを一括生成</button><button className="secondary" onClick={openFolder}><FolderOpen size={17} /> フォルダを開く</button><a className="button secondary" href={`/api/projects/${projectId}/zip`} onClick={e => { e.preventDefault(); fetch(`/api/projects/${projectId}/zip`, { method: 'POST' }).then(r => r.blob()).then(blob => { const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = `${projectId}.zip`; a.click(); URL.revokeObjectURL(a.href) }) }}><Download size={17} /> ZIP</a></div></div>
      <div className="video-grid">{articles.filter(article => article.script?.approved || article.video_path).map(article => <article className="video-card" key={article.id}>
        <div className="video-visual">{article.video_path ? <video controls preload="metadata" poster={`/api/articles/${article.id}/thumbnail`}><source src={`/api/articles/${article.id}/video`} type="video/mp4" /></video> : <div className="video-placeholder"><Video /><span>1080 × 1920</span></div>}</div>
        <div className="video-info"><StatusBadge status={article.status} /><h3>{article.title}</h3><p>{article.source}</p>{article.video_duration && <strong>{Number(article.video_duration).toFixed(1)}秒</strong>}{article.video_path && <a className="thumbnail-download" href={`/api/articles/${article.id}/thumbnail`} download>サムネイルを保存</a>}{article.error && <div className="error-note">{article.error}</div>}
          <button className="primary full" disabled={!!currentJob} onClick={() => startVideo(article)}>{article.video_path ? <><RefreshCw size={17} /> 再うp</> : <><Play size={17} /> ぶち上げろ！</>}</button>
        </div>
      </article>)}</div>
      {!articles.some(article => article.script?.approved || article.video_path) && <EmptyState icon={<Video />} title="承認済み原稿がありません" />}
    </section>}
  </>
}
