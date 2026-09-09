import { ArrowLeft, Check, ChevronRight, Copy, Download, FolderOpen, Image as ImageIcon, Play, RefreshCw, Sparkles, Video, X, Zap } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../api'
import ArticleCard from '../components/ArticleCard'
import EmptyState from '../components/EmptyState'
import ProgressPanel from '../components/ProgressPanel'
import ScriptEditor from '../components/ScriptEditor'
import StatusBadge from '../components/StatusBadge'
import type { Article, Job, Project } from '../types'

type Stage = 'articles' | 'scripts' | 'videos'
interface Props { projectId: string; initialJob?: Job | null; autoPipeline?: boolean; onBack: () => void; onError: (value: string) => void; onNotice: (value: string) => void }

export default function ProjectWorkspace({ projectId, initialJob, autoPipeline, onBack, onError, onNotice }: Props) {
  const [project, setProject] = useState<Project | null>(null)
  const [job, setJob] = useState<Job | null>(initialJob || null)
  const [stage, setStage] = useState<Stage>('articles')
  const [selected, setSelected] = useState<number[]>([])
  const [activeArticle, setActiveArticle] = useState<number | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [copiedId, setCopiedId] = useState<number | null>(null)
  const [copiedHashtagsId, setCopiedHashtagsId] = useState<number | null>(null)
  const [copiedDescriptionId, setCopiedDescriptionId] = useState<number | null>(null)
  const [settingsValues, setSettingsValues] = useState<Record<string, string | number | boolean>>({})
  const [bgmTracks, setBgmTracks] = useState<string[]>([])
  const [bgmFolder, setBgmFolder] = useState('')
  const autoPipelineTriggered = useRef(false)

  useEffect(() => { api.get<{ values: Record<string, string | number | boolean> }>('/settings').then(v => setSettingsValues(v.values)).catch(() => {}) }, [])
  useEffect(() => { api.get<{ tracks: string[]; folder: string }>('/bgm-tracks').then(v => { setBgmTracks(v.tracks); setBgmFolder(v.folder) }).catch(() => {}) }, [])

  const setArticleBgm = async (article: Article, track: string) => {
    try {
      await api.put(`/articles/${article.id}/bgm`, { bgm_track: track || null })
      setProject(current => current ? { ...current, articles: current.articles.map(a => a.id === article.id ? { ...a, bgm_track: track || null } : a) } : current)
    } catch (e) { onError(e instanceof Error ? e.message : String(e)) }
  }

  const buildDescription = (article: Article) => {
    const content = article.script?.content
    if (!content) return ''
    const template = String(settingsValues.youtube_description_template ?? '')
    const vars: Record<string, string> = {
      summary: content.youtube_summary || '', hashtags: (content.youtube_hashtags || []).join(' '),
      channel_name: String(settingsValues.channel_name ?? ''), channel_handle: String(settingsValues.channel_handle ?? ''),
      title: content.youtube_title || article.title,
    }
    return template.replace(/\{\{(\w+)\}\}/g, (_match, key) => vars[key] ?? '')
  }

  const copyTitle = async (articleId: number, title: string) => {
    try { await navigator.clipboard.writeText(title); setCopiedId(articleId); setTimeout(() => setCopiedId(null), 1500) } catch { onError('コピーに失敗しました。') }
  }
  const copyHashtags = async (articleId: number, hashtags: string[]) => {
    try { await navigator.clipboard.writeText(hashtags.join(' ')); setCopiedHashtagsId(articleId); setTimeout(() => setCopiedHashtagsId(null), 1500) } catch { onError('コピーに失敗しました。') }
  }
  const copyDescription = async (article: Article) => {
    try { await navigator.clipboard.writeText(buildDescription(article)); setCopiedDescriptionId(article.id); setTimeout(() => setCopiedDescriptionId(null), 1500) } catch { onError('コピーに失敗しました。') }
  }

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

  useEffect(() => {
    if (!autoPipeline || autoPipelineTriggered.current || !project) return
    if (project.status !== 'waiting_article_approval' || !project.articles.length) return
    autoPipelineTriggered.current = true
    const topArticleIds = [...project.articles]
      .sort((a, b) => b.combined_score - a.combined_score)
      .slice(0, project.article_count)
      .map(a => a.id)
    setSelected(topArticleIds)
    api.post<Job>(`/projects/${projectId}/full-pipeline`, { article_ids: topArticleIds })
      .then(newJob => { setJob(newJob); setStage('scripts'); onNotice(`${topArticleIds.length}件の記事を自動選定し、動画生成まで一気に実行します。`) })
      .catch(e => onError(e instanceof Error ? e.message : String(e)))
  }, [autoPipeline, project?.status, project?.articles.length])

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
  const runFullPipeline = async () => {
    if (!confirm(`${selected.length}記事について、原稿の自動承認を含めて動画生成まで一気に実行します。よろしいですか？`)) return
    try {
      const newJob = await api.post<Job>(`/projects/${projectId}/full-pipeline`, { article_ids: selected })
      setJob(newJob); setStage('scripts'); onNotice('動画生成までの一括処理を開始しました。')
    } catch (e) { onError(e instanceof Error ? e.message : String(e)) }
  }
  const startVideo = async (article: Article) => {
    try { const next = await api.post<Job>(`/articles/${article.id}/generate-video`); setJob(next); setStage('videos') } catch (e) { onError(e instanceof Error ? e.message : String(e)) }
  }
  const retryArticle = async (article: Article) => {
    try { const next = await api.post<Job>(`/articles/${article.id}/retry`); setJob(next); onNotice('この記事だけ再試行します。') } catch (e) { onError(e instanceof Error ? e.message : String(e)) }
  }
  const approveAllScripts = async () => {
    try {
      const result = await api.post<{ approved: number[]; failed: { article_id: number; title: string; error: string }[] }>(`/projects/${projectId}/approve-all-scripts`)
      await load()
      if (result.failed.length) onError(`${result.approved.length}件承認、${result.failed.length}件失敗: ${result.failed.map(f => f.title).join(', ')}`)
      else onNotice(`${result.approved.length}件の原稿を一括承認しました。`)
    } catch (e) { onError(e instanceof Error ? e.message : String(e)) }
  }
  const startVideoBatch = async () => {
    try { const next = await api.post<Job>(`/projects/${projectId}/generate-videos`); setJob(next); setStage('videos'); onNotice('承認済み動画の一括生成を開始しました。') } catch (e) { onError(e instanceof Error ? e.message : String(e)) }
  }
  const openFolder = async () => { try { await api.post(`/projects/${projectId}/open-folder`) } catch (e) { onError(e instanceof Error ? e.message : String(e)) } }
  const generateThumbnailPreview = async (article: Article) => {
    if (!article.script?.content) return
    setPreviewLoading(true)
    try {
      const response = await fetch(`/api/articles/${article.id}/preview-thumbnail`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(article.script.content) })
      if (!response.ok) throw new Error('Preview generation failed')
      const blob = await response.blob()
      setPreviewUrl(URL.createObjectURL(blob))
      onNotice('サムネイルプレビューを生成しました。')
    } catch (e) { onError(e instanceof Error ? e.message : 'プレビュー生成に失敗しました。') } finally { setPreviewLoading(false) }
  }

  if (!project) return <div className="loading">プロジェクトを読み込み中…</div>
  return <>
    <header className="workspace-head"><button className="back-button" onClick={onBack}><ArrowLeft size={17} /> 履歴へ</button><div><span>PROJECT</span><h1>{project.id}</h1></div><StatusBadge status={project.status} /></header>
    <div className="workflow-tabs">
      <button className={stage === 'articles' ? 'active' : ''} onClick={() => setStage('articles')}><span>1</span><div><b>記事選択</b><small>候補を承認</small></div></button><ChevronRight />
      <button className={stage === 'scripts' ? 'active' : ''} disabled={!scripted.length && !currentJob} onClick={() => setStage('scripts')}><span>2</span><div><b>原稿編集</b><small>確認と承認</small></div></button><ChevronRight />
      <button className={stage === 'videos' ? 'active' : ''} disabled={!articles.some(a => ['ready_for_video', 'generating_video', 'completed'].includes(a.status)) && !completedVideos.length} onClick={() => setStage('videos')}><span>3</span><div><b>動画生成</b><small>生成とレビュー</small></div></button>
    </div>
    {visibleJob && <ProgressPanel job={visibleJob} onError={onError} onCancelled={load} />}
    {project.error && <div className="error-banner">{project.error}</div>}

    {stage === 'articles' && <section>
      <div className="stage-title"><div><span className="eyebrow">ARTICLE CANDIDATES</span><h2>記事候補</h2></div><span className="selection-count"><b>{selected.length}</b>件選択中</span></div>
      {articles.length ? <div className="article-list">{articles.map(article => <ArticleCard key={article.id} article={article} checked={selected.includes(article.id)} onToggle={() => setSelected(selected.includes(article.id) ? selected.filter(id => id !== article.id) : [...selected, article.id])} />)}</div> :
        <EmptyState icon={<Sparkles />} title={currentJob ? '記事を探しています' : '候補がありません'} />}
      {!!articles.length && <div className="sticky-action"><span><Check size={18} /> {selected.length}件の記事を選択</span><div className="sticky-action-buttons"><button className="secondary big" disabled={!selected.length || !!currentJob} onClick={runFullPipeline}><Zap size={18} /> 動画生成まで一気に実行</button><button className="primary big" disabled={!selected.length || !!currentJob} onClick={approveArticles}>この{selected.length}記事で進む <ChevronRight size={18} /></button></div></div>}
    </section>}

    {stage === 'scripts' && <section>
      <div className="stage-title"><div><span className="eyebrow">SCRIPT WORKBENCH</span><h2>原稿編集</h2></div>{scripted.some(a => a.script && !a.script.approved) && <button className="primary" disabled={!!currentJob} onClick={approveAllScripts}><Check size={17} /> 未承認をすべて承認</button>}</div>
      {scripted.length ? <div className="editor-layout"><aside className="article-tabs">{scripted.map((article, index) => <button className={active?.id === article.id ? 'active' : ''} key={article.id} onClick={() => setActiveArticle(article.id)}><span>{String(index + 1).padStart(2, '0')}</span><div><b>{article.title}</b><small>{article.script?.approved ? '承認済み' : '編集待ち'} ・ {article.script?.estimated_seconds}s</small></div></button>)}</aside>
        <div className="editor-main">{active && <><div className="article-editor-head"><div><small>{active.source}</small><h2>{active.title}</h2></div><StatusBadge status={active.status} /></div>{active.error && <div className="retained-warning">{active.error}</div>}<ScriptEditor article={active} videoMode={project?.video_mode} onChanged={load} onError={onError} onNotice={onNotice} /></>}</div></div> :
        <EmptyState icon={<RefreshCw className={currentJob ? 'spin' : ''} />} title={currentJob ? '原稿を生成しています' : '原稿がありません'} />}
      {failedScripts.map(article => <div className="retry-row" key={article.id}><div><b>{article.title || article.url}</b><small>{article.error}</small></div><button className="secondary" disabled={!!currentJob} onClick={() => retryArticle(article)}><RefreshCw size={16} /> この記事だけ再試行</button></div>)}
      {scripted.some(a => a.script?.approved) && <div className="ready-strip"><div><Check /><span><b>承認済み原稿があります</b><small>動画生成へ進めます</small></span></div><button className="primary" onClick={() => setStage('videos')}>動画生成へ <ChevronRight size={17} /></button></div>}
    </section>}

    {stage === 'videos' && <section>
      <div className="stage-title"><div><span className="eyebrow">RENDER & REVIEW</span><h2>動画生成</h2></div><div className="inline-actions"><button className="primary" disabled={!!currentJob || !articles.some(article => article.script?.approved)} onClick={startVideoBatch}><Play size={17} /> 承認済みを一括生成</button><button className="secondary" onClick={openFolder}><FolderOpen size={17} /> フォルダを開く</button><a className="button secondary" href={`/api/projects/${projectId}/zip`} onClick={e => { e.preventDefault(); fetch(`/api/projects/${projectId}/zip`, { method: 'POST' }).then(r => r.blob()).then(blob => { const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = `${projectId}.zip`; a.click(); URL.revokeObjectURL(a.href) }) }}><Download size={17} /> ZIP</a></div></div>
      {bgmFolder && <p className="bgm-folder-hint">BGMに使う音楽ファイル（mp3/wav/m4a等）はこのフォルダに置いてください: <code>{bgmFolder}</code></p>}
      <div className="video-grid">{articles.filter(article => article.script?.approved || article.video_path).map(article => <article className="video-card" key={article.id}>
        <div className="video-visual">{article.video_path ? <video controls preload="metadata" poster={`/api/articles/${article.id}/thumbnail`}><source src={`/api/articles/${article.id}/video`} type="video/mp4" /></video> : <div className="video-placeholder"><Video /><span>1080 × 1920</span></div>}</div>
        <div className="video-info">
          <div className="video-info-head"><StatusBadge status={article.status} />{article.video_duration && <strong>{Number(article.video_duration).toFixed(1)}秒</strong>}</div>
          <h3>{article.title}</h3>
          {article.video_path && <a className="thumbnail-download" href={`/api/articles/${article.id}/thumbnail`} download>サムネイルを保存</a>}
          {article.error && <div className="error-note">{article.error}</div>}
          {(article.script?.content.youtube_title || article.script?.content.youtube_summary) && <details className="youtube-panel">
            <summary>YouTube用のタイトル・概要欄</summary>
            {article.script?.content.youtube_title && <div className="youtube-title-box">
              <small>Shorts用タイトル案</small>
              <div className="youtube-title-row"><span>{article.script.content.youtube_title}</span><button className="icon-button" aria-label="タイトルをコピー" onClick={() => copyTitle(article.id, article.script!.content.youtube_title!)}>{copiedId === article.id ? <Check size={16} /> : <Copy size={16} />}</button></div>
            </div>}
            {!!article.script?.content.youtube_hashtags?.length && <div className="youtube-title-box">
              <small>概要欄ハッシュタグ案</small>
              <div className="youtube-title-row"><span>{article.script.content.youtube_hashtags!.join(' ')}</span><button className="icon-button" aria-label="ハッシュタグをコピー" onClick={() => copyHashtags(article.id, article.script!.content.youtube_hashtags!)}>{copiedHashtagsId === article.id ? <Check size={16} /> : <Copy size={16} />}</button></div>
            </div>}
            {article.script?.content.youtube_summary && <div className="youtube-title-box">
              <div className="youtube-title-row"><small>概要欄 全文</small><button className="icon-button" aria-label="概要欄をコピー" onClick={() => copyDescription(article)}>{copiedDescriptionId === article.id ? <Check size={16} /> : <Copy size={16} />}</button></div>
              <pre className="youtube-description-text">{buildDescription(article)}</pre>
            </div>}
          </details>}
          <div className="bgm-select-row">
            <label htmlFor={`bgm-${article.id}`}>BGM</label>
            <select id={`bgm-${article.id}`} disabled={!!currentJob} value={article.bgm_track || ''} onChange={e => setArticleBgm(article, e.target.value)}>
              <option value="">おまかせ（アップロード曲からランダム）</option>
              {bgmTracks.map(track => <option key={track} value={track}>{track}</option>)}
            </select>
          </div>
          <div className="video-actions">
            <button className="video-action-preview" disabled={!!currentJob || previewLoading || !article.script?.content} onClick={() => generateThumbnailPreview(article)}><ImageIcon size={16} /> {previewLoading ? 'プレビュー中…' : 'サムネプレビュー'}</button>
            <button className="video-action-generate" disabled={!!currentJob} onClick={() => startVideo(article)}>{article.video_path ? <><RefreshCw size={17} /> 動画を再生成</> : <><Play size={17} /> 動画を生成</>}</button>
          </div>
        </div>
      </article>)}</div>
      {!articles.some(article => article.script?.approved || article.video_path) && <EmptyState icon={<Video />} title="承認済み原稿がありません" />}
    </section>}
    {previewUrl && <div className="modal-overlay" onClick={() => setPreviewUrl(null)}>
      <div className="modal-content preview-modal" onClick={e => e.stopPropagation()}>
        <button className="modal-close" onClick={() => setPreviewUrl(null)}><X size={24} /></button>
        <h2>サムネイルプレビュー</h2>
        <img src={previewUrl} alt="サムネイル" style={{ maxWidth: '100%', height: 'auto' }} />
      </div>
    </div>}
  </>
}
