import { Check, ClipboardPaste, Crown, ExternalLink, Link2, MessageSquare, Minus, Plus, Search, Sparkles, X, Zap } from 'lucide-react'
import { useState } from 'react'
import { api } from '../api'
import type { Job, Project } from '../types'

interface Props { onCreated: (project: Project, job: Job, autoPipeline?: boolean) => void; onError: (message: string) => void }

export default function NewProject({ onCreated, onError }: Props) {
  const [mode, setMode] = useState<'url' | 'request' | 'gonline'>('request')
  const [videoMode, setVideoMode] = useState<'normal' | 'gold'>('normal')
  const [urls, setUrls] = useState([''])
  const [requestText, setRequestText] = useState('')
  const [count, setCount] = useState(3)
  const [advanced, setAdvanced] = useState(false)
  const [busy, setBusy] = useState(false)

  const selectGonline = () => { setMode('gonline'); setVideoMode('gold') }

  const pasteUrl = async (index: number) => {
    try {
      const text = (await navigator.clipboard.readText()).trim()
      if (text) setUrls(urls.map((v, i) => i === index ? text : v))
    } catch { onError('クリップボードを読み取れませんでした。') }
  }

  const submit = async (autoPipeline = false) => {
    setBusy(true)
    try {
      const cleanUrls = urls.map(v => v.trim()).filter(Boolean)
      const project = await api.post<Project>('/projects', { mode, request_text: requestText, urls: cleanUrls, article_count: count, video_mode: videoMode })
      const job = await api.post<Job>(`/projects/${project.id}/discover`, { mode, request_text: requestText, urls: cleanUrls, article_count: count, video_mode: videoMode })
      onCreated(project, job, autoPipeline)
    } catch (error) { onError(error instanceof Error ? error.message : String(error)) }
    finally { setBusy(false) }
  }

  const canSubmit = mode === 'url' ? urls.some(url => url.trim()) : mode === 'request' ? Boolean(requestText.trim()) : true

  return <div className="new-project-page">
    <header className="page-head compact-head"><div><span className="eyebrow">NEW PROJECT</span><h1>新しいShortsを作成</h1></div><div className="new-project-actions"><a className="yahoo-link" href="https://news.yahoo.co.jp/" target="_blank" rel="noreferrer">ニュース <ExternalLink size={14} /></a><span className="step-caption"><Check size={15} /> 1 / 3</span></div></header>
    <div className="mode-grid mode-grid-three mode-switch">
      <button className={mode === 'request' ? 'mode-card active' : 'mode-card'} onClick={() => setMode('request')}><Search /><b>テーマ検索</b></button>
      <button className={mode === 'url' ? 'mode-card active' : 'mode-card'} onClick={() => setMode('url')}><Link2 /><b>URL指定</b></button>
      <button className={mode === 'gonline' ? 'mode-card active' : 'mode-card'} onClick={selectGonline}><Crown /><b>Gold検索</b><small>THE GOLD ONLINE</small></button>
    </div>
    <div className="mode-grid mode-grid-two mode-switch">
      <button className={videoMode === 'normal' ? 'mode-card active' : 'mode-card'} onClick={() => setVideoMode('normal')}><MessageSquare /><b>通常モード</b><small>コメント紹介のみ・60秒</small></button>
      <button className={videoMode === 'gold' ? 'mode-card active' : 'mode-card'} onClick={() => setVideoMode('gold')}><Crown /><b>Goldモード</b><small>詳しい解説＋コメント13件以上・尺は気にせず長め</small></button>
    </div>
    <section className="section-card form-card creation-form">
      {mode === 'url' ? <>
        <label className="field-label">Yahooニュースの記事URL</label>
        <div className="url-list">{urls.map((url, index) => <div className="url-row" key={index}>
          <Link2 size={18} /><input type="url" value={url} placeholder="https://news.yahoo.co.jp/articles/..." onChange={event => setUrls(urls.map((v, i) => i === index ? event.target.value : v))} />
          <button className="icon-button" aria-label="貼り付け" onClick={() => pasteUrl(index)}><ClipboardPaste size={18} /></button>
          {urls.length > 1 && <button className="icon-button" aria-label="URLを削除" onClick={() => setUrls(urls.filter((_, i) => i !== index))}><X size={18} /></button>}
        </div>)}</div>
        <button className="subtle" onClick={() => setUrls([...urls, ''])}><Plus size={16} /> URLを追加</button>
      </> : mode === 'gonline' ? <>
        <label className="field-label" htmlFor="request">絞り込み条件（任意）</label>
        <textarea id="request" rows={4} value={requestText} onChange={event => setRequestText(event.target.value)} placeholder="空欄なら新着・コメント数の多い記事から自動選定。例：不動産投資に関する記事" />
        <div className="count-row"><div><b>記事数</b></div><div className="stepper"><button onClick={() => setCount(Math.max(1, count - 1))}><Minus size={16} /></button><b>{count}</b><button onClick={() => setCount(Math.min(10, count + 1))}><Plus size={16} /></button></div></div>
      </> : <>
        <label className="field-label" htmlFor="request">テーマ</label>
        <textarea id="request" rows={6} value={requestText} onChange={event => setRequestText(event.target.value)} placeholder="例：生成AI関連の記事" />
        <div className="count-row"><div><b>記事数</b></div><div className="stepper"><button onClick={() => setCount(Math.max(1, count - 1))}><Minus size={16} /></button><b>{count}</b><button onClick={() => setCount(Math.min(10, count + 1))}><Plus size={16} /></button></div></div>
      </>}
      <button className="advanced-toggle" onClick={() => setAdvanced(!advanced)}>詳細設定 <span>{advanced ? '−' : '+'}</span></button>
      {advanced && <div className="advanced-note">設定画面で変更できます。</div>}
      <div className="form-actions">
        <button className="secondary big" disabled={busy || !canSubmit} onClick={() => submit(true)}><Zap size={18} /> 動画生成まで一気に実行</button>
        <button className="primary big" disabled={busy || !canSubmit} onClick={() => submit(false)}><Sparkles size={18} /> {busy ? '準備中…' : mode === 'url' ? '記事を取得' : '記事を探す'}</button>
      </div>
    </section>
  </div>
}
