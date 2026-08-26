import { CheckCircle2, GripVertical, Plus, RefreshCw, Save, Trash2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { api } from '../api'
import type { Article, Post, ScriptContent } from '../types'

interface Props { article: Article; onChanged: () => void; onError: (value: string) => void; onNotice: (value: string) => void }

const blankPost = (): Post => ({ text: '', reply_to: null, tone: 'rough', importance: 3, source_comment_ids: [] })
const estimate = (script: ScriptContent) => {
  const seconds = (text: string) => text.trim() ? .45 + text.trim().length / 7.6 : 0
  return seconds(script.intro.narration) + script.posts.reduce((sum, post) => sum + seconds(post.text) + .05, 0) + seconds(script.outro.narration) + .1
}

export default function ScriptEditor({ article, onChanged, onError, onNotice }: Props) {
  const [script, setScript] = useState<ScriptContent | null>(article.script?.content || null)
  const [busy, setBusy] = useState(false)
  const [dragIndex, setDragIndex] = useState<number | null>(null)
  useEffect(() => setScript(article.script?.content || null), [article.id, article.script?.content])
  if (!script) return <div className="empty-inline"><p>この記事の原稿はまだありません。</p>{article.error && <div className="error-note">{article.error}</div>}</div>

  const mutatePost = (index: number, values: Partial<Post>) => setScript({ ...script, posts: script.posts.map((post, i) => i === index ? { ...post, ...values } : post) })
  const remove = (index: number) => {
    const removedNumber = index + 1
    setScript({ ...script, posts: script.posts.filter((_, i) => i !== index).map(post => ({ ...post, reply_to: post.reply_to === removedNumber ? null : post.reply_to && post.reply_to > removedNumber ? post.reply_to - 1 : post.reply_to })) })
  }
  const reorder = (from: number, to: number) => {
    if (from === to) return
    const indexed = script.posts.map((post, index) => ({ post, old: index + 1 }))
    const [moving] = indexed.splice(from, 1); indexed.splice(to, 0, moving)
    const mapping = new Map(indexed.map((item, index) => [item.old, index + 1]))
    const posts = indexed.map((item, index) => {
      const target = item.post.reply_to ? mapping.get(item.post.reply_to) || null : null
      return { ...item.post, reply_to: target && target < index + 1 ? target : null }
    })
    setScript({ ...script, posts })
  }
  const save = async () => {
    const cleaned = { ...script, posts: script.posts.filter(post => post.text.trim()) }
    setBusy(true); try { await api.put(`/articles/${article.id}/script`, { script: cleaned }); onNotice('原稿を保存しました。'); onChanged() } catch (e) { onError(e instanceof Error ? e.message : String(e)) } finally { setBusy(false) }
  }
  const regenerate = async () => {
    if (!confirm('現在の編集内容を破棄して、コメント原稿を再生成しますか？')) return
    setBusy(true); try { await api.post(`/articles/${article.id}/script/regenerate`); onNotice('原稿を再生成しました。'); onChanged() } catch (e) { onError(e instanceof Error ? e.message : String(e)) } finally { setBusy(false) }
  }
  const approve = async () => {
    setBusy(true); try { await api.put(`/articles/${article.id}/script`, { script: { ...script, posts: script.posts.filter(post => post.text.trim()) } }); await api.post(`/articles/${article.id}/script/approve`); onNotice('原稿を承認しました。'); onChanged() } catch (e) { onError(e instanceof Error ? e.message : String(e)) } finally { setBusy(false) }
  }
  const estimated = estimate(script)
  return <div className="script-editor">
    <div className="editor-block"><span className="block-number">01</span><div className="block-body"><h3>記事説明</h3>
      <label>見出し<input value={script.intro.headline} onChange={e => setScript({ ...script, intro: { ...script.intro, headline: e.target.value } })} /></label>
      <label>画面の補足<textarea rows={2} value={script.intro.explainer} onChange={e => setScript({ ...script, intro: { ...script.intro, explainer: e.target.value } })} /></label>
      <label>記事説明音声<textarea rows={2} value={script.intro.narration} onChange={e => setScript({ ...script, intro: { ...script.intro, narration: e.target.value } })} /></label>
    </div></div>
    <div className="comments-head"><div><h3>コメント</h3><p>{script.posts.length}レス ・ ドラッグして並び替え</p></div><button className="secondary" onClick={regenerate} disabled={busy}><RefreshCw size={16} /> 全コメント再生成</button></div>
    <div className="post-list">{script.posts.map((post, index) => <div key={index} className="post-editor" draggable onDragStart={() => setDragIndex(index)} onDragOver={e => e.preventDefault()} onDrop={() => { if (dragIndex !== null) reorder(dragIndex, index); setDragIndex(null) }}>
      <span className="drag"><GripVertical /></span><span className="post-number">{index + 1}</span>
      <div className="post-fields"><textarea rows={2} value={post.text} placeholder="コメントを入力" onChange={e => mutatePost(index, { text: e.target.value })} />
        <div className="post-options"><label>返信先<select value={post.reply_to ?? ''} onChange={e => mutatePost(index, { reply_to: e.target.value ? Number(e.target.value) : null })}><option value="">返信なし</option>{script.posts.slice(0, index).map((_, i) => <option key={i} value={i + 1}>レス{i + 1}へ返信</option>)}</select></label>
          <label>重要度<select value={post.importance} onChange={e => mutatePost(index, { importance: Number(e.target.value) })}>{[1, 2, 3, 4, 5].map(v => <option key={v}>{v}</option>)}</select></label><span>{post.text.length}文字</span></div>
      </div><button className="icon-button danger" onClick={() => remove(index)} aria-label={`レス${index + 1}を削除`}><Trash2 size={18} /></button>
    </div>)}</div>
    <button className="add-post" onClick={() => setScript({ ...script, posts: [...script.posts, blankPost()] })}><Plus size={17} /> コメントを追加</button>
    <div className="editor-block outro-block"><span className="block-number">03</span><div className="block-body"><h3>アウトロ</h3><label>画面テキスト<input value={script.outro.text} onChange={e => setScript({ ...script, outro: { ...script.outro, text: e.target.value } })} /></label><label>ナレーション<input value={script.outro.narration} onChange={e => setScript({ ...script, outro: { ...script.outro, narration: e.target.value } })} /></label></div></div>
    <div className="approval-bar"><div><small>推定動画時間</small><b className={estimated > 59.5 ? 'over' : ''}>{estimated.toFixed(1)}秒</b><span>/ 59.5秒以内</span></div><div><button className="secondary" disabled={busy} onClick={save}><Save size={17} /> 下書き保存</button><button className="primary" disabled={busy || estimated > 59.5} onClick={approve}><CheckCircle2 size={17} /> この原稿を承認</button></div></div>
  </div>
}

