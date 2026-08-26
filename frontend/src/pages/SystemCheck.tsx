import { CheckCircle2, CircleAlert, RefreshCw, Stethoscope } from 'lucide-react'
import { useEffect, useState } from 'react'
import { api } from '../api'

interface Check { name: string; ok: boolean; detail: string; install: string }

export default function SystemCheck({ onError }: { onError: (message: string) => void }) {
  const [checks, setChecks] = useState<Check[]>([])
  const [loading, setLoading] = useState(false)
  const run = async (full = false) => { setLoading(true); try { setChecks((await api.get<{ checks: Check[] }>(`/system/check?check_yahoo=${full}&check_tts=${full}`)).checks) } catch (e) { onError(e instanceof Error ? e.message : String(e)) } finally { setLoading(false) } }
  useEffect(() => { run() }, [])
  return <>
    <header className="page-head"><div><span className="eyebrow">PREFLIGHT</span><h1>System Status</h1><p>ローカル生成環境の依存関係を確認します。</p></div><button className="secondary" onClick={() => run(true)} disabled={loading}><RefreshCw className={loading ? 'spin' : ''} size={18} /> 再チェック</button></header>
    <section className="section-card system-card">
      <div className="system-summary"><span><Stethoscope /></span><div><h2>{checks.filter(c => c.ok).length} / {checks.length} checks passed</h2><p>不足項目は案内に従ってインストールしてください。アプリがapt-getを実行することはありません。</p></div></div>
      <div className="check-list">{checks.map(check => <div className="check-row" key={check.name}>
        <span className={`check-icon ${check.ok ? 'ok' : 'ng'}`}>{check.ok ? <CheckCircle2 /> : <CircleAlert />}</span>
        <div><b>{check.name}</b><small>{check.detail}</small>{!check.ok && check.install && <p>{check.install}</p>}</div><strong className={check.ok ? 'ok-text' : 'ng-text'}>{check.ok ? 'OK' : 'ACTION'}</strong>
      </div>)}</div>
    </section>
  </>
}
