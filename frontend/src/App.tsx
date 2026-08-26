import { AlertCircle, CheckCircle2, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { api } from './api'
import Shell, { type Page } from './components/Shell'
import Dashboard from './pages/Dashboard'
import History from './pages/History'
import NewProject from './pages/NewProject'
import ProjectWorkspace from './pages/ProjectWorkspace'
import SettingsPage from './pages/Settings'
import SystemCheck from './pages/SystemCheck'
import type { Job, Project, ProjectSummary } from './types'

function routeFromHash(): { page: Page; projectId?: string } {
  const value = location.hash.replace(/^#\/?/, '')
  if (value.startsWith('project/')) return { page: 'project', projectId: value.split('/')[1] }
  if (['dashboard', 'new', 'history', 'settings', 'system'].includes(value)) return { page: value as Page }
  return { page: 'dashboard' }
}

export default function App() {
  const [route, setRoute] = useState(routeFromHash())
  const [projects, setProjects] = useState<ProjectSummary[]>([])
  const [initialJob, setInitialJob] = useState<Job | null>(null)
  const [toast, setToast] = useState<{ kind: 'error' | 'notice'; text: string } | null>(null)
  const notify = (kind: 'error' | 'notice', text: string) => { setToast({ kind, text }); window.setTimeout(() => setToast(null), 5200) }
  const loadProjects = () => api.get<{ projects: ProjectSummary[] }>('/projects').then(result => setProjects(result.projects)).catch(error => notify('error', error.message))
  useEffect(() => {
    loadProjects()
    if (!location.hash) {
      api.get<{ openai: { registered: boolean } }>('/settings').then(result => {
        if (!result.openai.registered) navigate('settings')
      }).catch(() => undefined)
    }
    const listener = () => setRoute(routeFromHash())
    addEventListener('hashchange', listener)
    return () => removeEventListener('hashchange', listener)
  }, [])
  const navigate = (page: Page, projectId?: string) => { location.hash = page === 'project' ? `#/project/${projectId}` : `#/${page}` }
  const openProject = (id: string) => { setInitialJob(null); navigate('project', id) }
  const created = (project: Project, job: Job) => { setInitialJob(job); loadProjects(); navigate('project', project.id) }
  return <Shell page={route.page} onNavigate={page => navigate(page)}>
    {route.page === 'dashboard' && <Dashboard projects={projects} onNew={() => navigate('new')} onOpen={openProject} />}
    {route.page === 'new' && <NewProject onCreated={created} onError={text => notify('error', text)} />}
    {route.page === 'history' && <History projects={projects} onOpen={openProject} />}
    {route.page === 'settings' && <SettingsPage onError={text => notify('error', text)} onNotice={text => notify('notice', text)} />}
    {route.page === 'system' && <SystemCheck onError={text => notify('error', text)} />}
    {route.page === 'project' && route.projectId && <ProjectWorkspace projectId={route.projectId} initialJob={initialJob} onBack={() => { loadProjects(); navigate('history') }} onError={text => notify('error', text)} onNotice={text => notify('notice', text)} />}
    {toast && <div className={`toast ${toast.kind}`}>{toast.kind === 'error' ? <AlertCircle /> : <CheckCircle2 />}<span>{toast.text}</span><button onClick={() => setToast(null)}><X /></button></div>}
  </Shell>
}
