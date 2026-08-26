import { Bot, Link2, Minus, Plus, Search, Sparkles, X } from 'lucide-react'
import { useState } from 'react'
import { api } from '../api'
import type { Job, Project } from '../types'

interface Props { onCreated: (project: Project, job: Job) => void; onError: (message: string) => void }

export default function NewProject({ onCreated, onError }: Props) {
  const [mode, setMode] = useState<'url' | 'request' | 'auto'>('url')
  const [urls, setUrls] = useState([''])
  const [requestText, setRequestText] = useState('')
  const [count, setCount] = useState(3)
  const [advanced, setAdvanced] = useState(false)
  const [busy, setBusy] = useState(false)

  const submit = async () => {
    setBusy(true)
    try {
      const cleanUrls = urls.map(v => v.trim()).filter(Boolean)
      const project = await api.post<Project>('/projects', { mode, request_text: requestText, urls: cleanUrls, article_count: count })
      const job = await api.post<Job>(`/projects/${project.id}/discover`, { mode, request_text: requestText, urls: cleanUrls, article_count: count })
      onCreated(project, job)
    } catch (error) { onError(error instanceof Error ? error.message : String(error)) }
    finally { setBusy(false) }
  }

  const canSubmit = mode === 'url' ? urls.some(url => url.trim()) : Boolean(requestText.trim())

  return <>
    <header className="page-head"><div><span className="eyebrow">NEW PROJECT</span><h1>新しいShortsを作成</h1><p>記事の指定方法を選び、候補を探します。</p></div></header>
    <div className="mode-grid">
      <button className={mode === 'url' ? 'mode-card active' : 'mode-card'} onClick={() => setMode('url')}><Link2 /><b>URLを直接指定</b><span>使いたいYahoo記事が決まっている</span></button>
      <button className={mode === 'request' ? 'mode-card active' : 'mode-card'} onClick={() => setMode('request')}><Search /><b>自然言語で指定</b><span>テーマや人物、必要本数で探す</span></button>
      <button className={mode === 'auto' ? 'mode-card active' : 'mode-card'} onClick={() => setMode('auto')}><Bot /><b>AIにおまかせ</b><span>盛り上がる記事を自動選定</span></button>
    </div>
    <section className="section-card form-card">
      {mode === 'url' ? <>
        <label className="field-label">Yahooニュースの記事URL</label>
        <div className="url-list">{urls.map((url, index) => <div className="url-row" key={index}>
          <Link2 size={18} /><input type="url" value={url} placeholder="https://news.yahoo.co.jp/articles/..." onChange={event => setUrls(urls.map((v, i) => i === index ? event.target.value : v))} />
          {urls.length > 1 && <button className="icon-button" aria-label="URLを削除" onClick={() => setUrls(urls.filter((_, i) => i !== index))}><X size={18} /></button>}
        </div>)}</div>
        <button className="subtle" onClick={() => setUrls([...urls, ''])}><Plus size={16} /> URLを追加</button>
      </> : <>
        <label className="field-label" htmlFor="request">{mode === 'request' ? '探したい記事' : 'AIへの選定リクエスト'}</label>
        <textarea id="request" rows={6} value={requestText} onChange={event => setRequestText(event.target.value)} placeholder={mode === 'request' ? '例：生成AI関連の記事を2本' : '例：直近のニュースから、コメント欄が活発で議論になりそうな記事を選んで'} />
        <div className="count-row"><div><b>生成本数</b><small>候補として選定する記事数</small></div><div className="stepper"><button onClick={() => setCount(Math.max(1, count - 1))}><Minus size={16} /></button><b>{count}</b><button onClick={() => setCount(Math.min(10, count + 1))}><Plus size={16} /></button></div></div>
      </>}
      <button className="advanced-toggle" onClick={() => setAdvanced(!advanced)}>詳細な探索設定 <span>{advanced ? '−' : '+'}</span></button>
      {advanced && <div className="advanced-note">検索元、最大経過時間、スコア配分は「設定 → Yahoo」から変更できます。</div>}
      <div className="form-actions"><button className="primary big" disabled={busy || !canSubmit} onClick={submit}><Sparkles size={18} /> {busy ? '準備中…' : mode === 'url' ? '記事を取得' : '記事を探す'}</button></div>
    </section>
  </>
}
