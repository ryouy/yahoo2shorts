import { CheckCircle2, Eye, EyeOff, KeyRound, Save, Trash2, Zap } from 'lucide-react'
import { useEffect, useState } from 'react'
import { api } from '../api'
import SystemCheck from './SystemCheck'

interface Payload { values: Record<string, string | number | boolean>; openai: { registered: boolean; masked_key: string | null } }
interface Props { onError: (message: string) => void; onNotice: (message: string) => void }

const groups = [
  { name: 'General', description: 'プロジェクトと保存先', fields: [
    ['article_count', '標準の記事本数', 'number'], ['output_folder', '成果物フォルダ', 'text'],
  ]},
  { name: 'Yahoo', description: '探索とコメント取得', fields: [
    ['comment_limit', '取得コメント上限', 'number'], ['max_comment_pages', '最大ページ数', 'number'], ['max_article_age_hours', '記事最大経過時間', 'number'], ['include_replies', '返信を取得', 'boolean'],
    ['use_yahoo_search', 'Yahoo検索', 'boolean'], ['use_yahoo_top', 'Yahooトップ', 'boolean'], ['use_yahoo_ranking', 'Yahooランキング', 'boolean'], ['use_yahoo_categories', 'Yahooカテゴリ', 'boolean'],
  ]},
  { name: 'Script', description: '原稿の長さと構成', fields: [
    ['thread_post_min', 'レス最低数', 'number'], ['thread_post_max', 'レス最大数', 'number'], ['post_max_chars', '最大文字数', 'number'], ['target_video_seconds', '目標時間（秒）', 'number'], ['hard_max_video_seconds', '最大時間（秒）', 'number'],
  ]},
  { name: 'Voice', description: 'edge-tts 音声', fields: [
    ['voice_1', 'Voice 1（Nanami / 日本語）', 'text'], ['voice_2', 'Voice 2（Keita / 日本語）', 'text'], ['voice_3', 'Voice 3（Ava / 多言語）', 'text'],
    ['voice_4', 'Voice 4（Andrew / 多言語）', 'text'], ['voice_5', 'Voice 5（Emma / 多言語）', 'text'], ['voice_6', 'Voice 6（Brian / 多言語）', 'text'], ['voice_rate', 'Voice Rate', 'text'],
  ]},
  { name: 'Video', description: '縦型動画とBGM', fields: [
    ['width', '幅', 'number'], ['height', '高さ', 'number'], ['fps', 'FPS', 'number'], ['comments_per_page', 'コメント/ページ', 'number'], ['bgm_enabled', 'BGM', 'boolean'], ['bgm_volume', 'BGM Volume', 'number'], ['bgm_bpm', 'BPM', 'number'],
  ]},
] as const

export default function SettingsPage({ onError, onNotice }: Props) {
  const [data, setData] = useState<Payload | null>(null)
  const [apiKey, setApiKey] = useState('')
  const [show, setShow] = useState(false)
  const [testing, setTesting] = useState(false)
  useEffect(() => { api.get<Payload>('/settings').then(setData).catch(e => onError(e.message)) }, [])
  const update = (key: string, value: string | number | boolean) => setData(data ? { ...data, values: { ...data.values, [key]: value } } : data)
  const save = async () => {
    if (!data) return
    try { const result = await api.put<{ values: Payload['values'] }>('/settings', { values: data.values }); setData({ ...data, values: result.values }); onNotice('設定を保存しました。') } catch (e) { onError(e instanceof Error ? e.message : String(e)) }
  }
  const saveKey = async () => {
    try { const openai = await api.put<Payload['openai'] & { storage: string }>('/settings/openai-key', { api_key: apiKey }); setData(data && { ...data, openai }); setApiKey(''); onNotice(openai.storage === 'os_keychain' ? 'APIキーをOS Keychainへ保存しました。' : 'APIキーをローカルSecret Storeへ保存しました。') } catch (e) { onError(e instanceof Error ? e.message : String(e)) }
  }
  const test = async () => {
    setTesting(true); try { const result = await api.post<{ ok: boolean; model_available: boolean }>('/settings/openai-test'); onNotice(result.model_available ? 'OpenAI接続とモデル利用を確認しました。' : '接続成功。ただし設定モデルは一覧にありません。') } catch (e) { onError(e instanceof Error ? e.message : String(e)) } finally { setTesting(false) }
  }
  const removeKey = async () => {
    if (!confirm('登録済みのOpenAI APIキーを削除しますか？')) return
    try { const openai = await api.delete<Payload['openai']>('/settings/openai-key'); setData(data && { ...data, openai }); onNotice('APIキーを削除しました。') } catch (e) { onError(e instanceof Error ? e.message : String(e)) }
  }
  if (!data) return <div className="loading">設定を読み込み中…</div>
  return <>
    <header className="page-head compact-head"><div><span className="eyebrow">PREFERENCES</span><h1>設定</h1></div><button className="primary" onClick={save}><Save size={18} /> 保存</button></header>
    <section className="section-card key-card">
      <div className="setting-heading"><span className="setting-icon green"><KeyRound /></span><div><h2>OpenAI</h2></div><span className={`connection ${data.openai.registered ? 'ok' : ''}`}>{data.openai.registered ? <><CheckCircle2 size={15} /> 登録済み</> : '未登録'}</span></div>
      <div className="key-content">
        {data.openai.registered && <div className="masked-key"><span>API Key</span><code>{data.openai.masked_key}</code></div>}
        <label className="field-label" htmlFor="api-key">{data.openai.registered ? '新しいキーへ変更' : 'API Key'}</label>
        <div className="key-input"><input id="api-key" type={show ? 'text' : 'password'} value={apiKey} placeholder="sk-..." autoComplete="off" onChange={e => setApiKey(e.target.value)} /><button onClick={() => setShow(!show)} aria-label="キー表示切替">{show ? <EyeOff /> : <Eye />}</button></div>
        <div className="inline-actions"><button className="primary" disabled={!apiKey} onClick={saveKey}><Save size={16} /> 保存</button>{data.openai.registered && <><button className="secondary" disabled={testing} onClick={test}><Zap size={16} /> {testing ? '確認中…' : '接続テスト'}</button><button className="danger-button" onClick={removeKey}><Trash2 size={16} /> 削除</button></>}</div>
      </div>
      <div className="setting-row single"><label>使用モデル<span>OpenAI Responses API</span></label><input value={String(data.values.openai_model)} onChange={e => update('openai_model', e.target.value)} /></div>
    </section>
    {groups.map(group => <details className="settings-disclosure" key={group.name} open={group.name === 'General'}>
      <summary><span>{group.name}</span><span>⌄</span></summary>
      <div className="settings-grid">{group.fields.map(([key, label, type]) => <div className="setting-row" key={key}>
        <label htmlFor={key}>{label}</label>
        {type === 'boolean' ? <button id={key} className={`toggle ${data.values[key] ? 'on' : ''}`} onClick={() => update(key, !data.values[key])}><span /></button> : <input id={key} type={type} step={key.includes('volume') ? '.001' : key.includes('seconds') ? '.1' : '1'} value={String(data.values[key])} onChange={e => update(key, type === 'number' ? Number(e.target.value) : e.target.value)} />}
      </div>)}</div>
    </details>)}
    <details className="settings-disclosure"><summary><span>システム</span><span>⌄</span></summary><SystemCheck embedded onError={onError} /></details>
  </>
}
