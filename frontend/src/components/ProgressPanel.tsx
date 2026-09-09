import { AlertTriangle, CheckCircle2, ChevronDown, LoaderCircle, XCircle } from 'lucide-react'
import { useState } from 'react'
import { api } from '../api'
import type { Job } from '../types'

interface Props { job: Job; onError?: (value: string) => void; onCancelled?: () => void }

export default function ProgressPanel({ job, onError, onCancelled }: Props) {
  const [logsOpen, setLogsOpen] = useState(false)
  const [cancelling, setCancelling] = useState(false)
  const Icon = job.status === 'error' ? AlertTriangle : job.status === 'completed' ? CheckCircle2 : LoaderCircle
  const cancellable = job.status === 'queued' || job.status === 'running'

  const cancelJob = async () => {
    setCancelling(true)
    try { await api.post(`/jobs/${job.id}/cancel`); onCancelled?.() } catch (e) { onError?.(e instanceof Error ? e.message : String(e)) } finally { setCancelling(false) }
  }

  return <section className={`progress-panel ${job.status}`}>
    <div className="progress-title">
      <span className="progress-icon"><Icon size={22} className={job.status === 'running' ? 'spin' : ''} /></span>
      <div><strong>{job.stage}</strong><small>{job.status === 'error' ? job.error : `${job.progress}% 完了`}</small></div>
      <b>{job.progress}%</b>
      {cancellable && <button className="cancel-job-button" disabled={cancelling || job.status === 'cancelling'} onClick={cancelJob}><XCircle size={16} /> {job.status === 'cancelling' ? 'キャンセル中…' : 'キャンセル'}</button>}
    </div>
    <div className="progress-track"><span style={{ width: `${job.progress}%` }} /></div>
    <button className="log-toggle" onClick={() => setLogsOpen(!logsOpen)}><ChevronDown size={16} /> 詳細ログ</button>
    {logsOpen && <div className="logs">{job.logs.length ? job.logs.map((log, i) => <div key={i}><time>{new Date(log.at).toLocaleTimeString('ja-JP')}</time>{log.message}</div>) : 'ログはまだありません。'}</div>}
  </section>
}

