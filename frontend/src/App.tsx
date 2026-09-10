import { AlertCircle, CheckCircle2, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { api, ApiError } from './api'
import Shell, { type Page } from './components/Shell'
import Dashboard from './pages/Dashboard'
import NewProject from './pages/NewProject'
import ProjectWorkspace from './pages/ProjectWorkspace'
import SettingsPage from './pages/Settings'
import UsedArticles from './pages/UsedArticles'
import type { Job, Project, ProjectSummary } from './types'

function routeFromHash(): { page: Page; projectId?: string } {
  const value = location.hash.replace(/^#\/?/, '')
  if (value.startsWith('project/')) return { page: 'project', projectId: value.split('/')[1] }
  if (value === 'system') return { page: 'settings' }
  if (['dashboard', 'new', 'settings', 'used-articles'].includes(value)) return { page: value as Page }
  return { page: 'dashboard' }
}

export default function App() {
  const [route, setRoute] = useState(routeFromHash())
  const [projects, setProjects] = useState<ProjectSummary[]>([])
  const [initialJob, setInitialJob] = useState<Job | null>(null)
  const [autoPipelineId, setAutoPipelineId] = useState<string | null>(null)
  const [toast, setToast] = useState<{ kind: 'error' | 'notice'; text: string } | null>(null)
  const notify = (kind: 'error' | 'notice', text: string) => { setToast({ kind, text }); window.setTimeout(() => setToast(null), 5200) }
  const loadProjects = () => api.get<{ projects: ProjectSummary[] }>('/projects').then(result => setProjects(result.projects)).catch(error => notify('error', error.message))
  useEffect(() => {
    loadProjects()
    const refresh = window.setInterval(loadProjects, 2500)
    if (!location.hash) {
      api.get<{ openai: { registered: boolean } }>('/settings').then(result => {
        if (!result.openai.registered) navigate('settings')
      }).catch(() => undefined)
    }
    const listener = () => setRoute(routeFromHash())
    addEventListener('hashchange', listener)
    return () => { removeEventListener('hashchange', listener); window.clearInterval(refresh) }
  }, [])
  const navigate = (page: Page, projectId?: string) => { location.hash = page === 'project' ? `#/project/${projectId}` : `#/${page}` }
  const openProject = (id: string) => { setInitialJob(null); navigate('project', id) }
  const created = (project: Project, job: Job, autoPipeline = false) => { setInitialJob(job); setAutoPipelineId(autoPipeline ? project.id : null); loadProjects(); navigate('project', project.id) }
  const deleteProject = async (id: string, force = false): Promise<void> => {
    try {
      await api.delete<void>(`/projects/${id}${force ? '?force=true' : ''}`)
      setProjects(current => current.filter(project => project.id !== id))
      notify('notice', force ? '処理を強制停止してプロジェクトを削除しました。' : 'プロジェクトを削除しました。')
    } catch (error) {
      if (error instanceof ApiError && error.status === 409 && !force) {
        if (confirm('このプロジェクトは処理中です。強制的に停止して削除しますか？')) return deleteProject(id, true)
        return
      }
      notify('error', error instanceof Error ? error.message : String(error))
    }
  }
  const deleteManyProjects = async (ids: string[]): Promise<void> => {
    const results = await Promise.allSettled(ids.map(id => api.delete<void>(`/projects/${id}`)))
    const succeeded = ids.filter((_, index) => results[index].status === 'fulfilled')
    const failed = ids.length - succeeded.length
    setProjects(current => current.filter(project => !succeeded.includes(project.id)))
    if (failed > 0) notify('error', `${succeeded.length}件を削除しました。${failed}件は処理中のため削除できませんでした。`)
    else notify('notice', `${succeeded.length}件のプロジェクトを削除しました。`)
  }
  return <Shell page={route.page} onNavigate={page => navigate(page)}>
    {route.page === 'dashboard' && <Dashboard projects={projects} onNew={() => navigate('new')} onOpen={openProject} onDelete={deleteProject} onDeleteMany={deleteManyProjects} onOpenUsedArticles={() => navigate('used-articles')} />}
    {route.page === 'used-articles' && <UsedArticles onBack={() => navigate('dashboard')} onError={text => notify('error', text)} />}
    {route.page === 'new' && <NewProject onCreated={created} onError={text => notify('error', text)} />}
    {route.page === 'settings' && <SettingsPage onError={text => notify('error', text)} onNotice={text => notify('notice', text)} />}
    {route.page === 'project' && route.projectId && <ProjectWorkspace projectId={route.projectId} initialJob={initialJob} autoPipeline={autoPipelineId === route.projectId} onBack={() => { loadProjects(); navigate('dashboard') }} onError={text => notify('error', text)} onNotice={text => notify('notice', text)} />}
    {toast && <div className={`toast ${toast.kind}`}>{toast.kind === 'error' ? <AlertCircle /> : <CheckCircle2 />}<span>{toast.text}</span><button onClick={() => setToast(null)}><X /></button></div>}
  </Shell>
}
