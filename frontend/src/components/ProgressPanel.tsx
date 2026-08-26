import { AlertTriangle, CheckCircle2, ChevronDown, LoaderCircle } from 'lucide-react'
import { useState } from 'react'
import type { Job } from '../types'

export default function ProgressPanel({ job }: { job: Job }) {
  const [logsOpen, setLogsOpen] = useState(false)
  const Icon = job.status === 'error' ? AlertTriangle : job.status === 'completed' ? CheckCircle2 : LoaderCircle
  return <section className={`progress-panel ${job.status}`}>
    <div className="progress-title">
      <span className="progress-icon"><Icon size={22} className={job.status === 'running' ? 'spin' : ''} /></span>
      <div><strong>{job.stage}</strong><small>{job.status === 'error' ? job.error : `${job.progress}% 完了`}</small></div>
      <b>{job.progress}%</b>
    </div>
    <div className="progress-track"><span style={{ width: `${job.progress}%` }} /></div>
    <button className="log-toggle" onClick={() => setLogsOpen(!logsOpen)}><ChevronDown size={16} /> 詳細ログ</button>
    {logsOpen && <div className="logs">{job.logs.length ? job.logs.map((log, i) => <div key={i}><time>{new Date(log.at).toLocaleTimeString('ja-JP')}</time>{log.message}</div>) : 'ログはまだありません。'}</div>}
  </section>
}

