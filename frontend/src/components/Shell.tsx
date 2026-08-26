import type { ReactNode } from 'react'
import { Clapperboard, FilePlus2, Gauge, History, PanelLeftClose, Settings, Stethoscope } from 'lucide-react'

export type Page = 'dashboard' | 'new' | 'history' | 'settings' | 'system' | 'project'

interface Props {
  page: Page
  onNavigate: (page: Page) => void
  children: ReactNode
}

const items: { id: Page; label: string; icon: typeof Gauge }[] = [
  { id: 'dashboard', label: 'ダッシュボード', icon: Gauge },
  { id: 'new', label: '新規作成', icon: FilePlus2 },
  { id: 'history', label: '履歴', icon: History },
  { id: 'settings', label: '設定', icon: Settings },
  { id: 'system', label: 'システム', icon: Stethoscope },
]

export default function Shell({ page, onNavigate, children }: Props) {
  return <div className="app-shell">
    <aside className="sidebar">
      <button className="brand" onClick={() => onNavigate('dashboard')}>
        <span className="brand-mark"><Clapperboard size={23} /></span>
        <span><b>Yahoo Shorts</b><small>STUDIO</small></span>
      </button>
      <nav aria-label="メインナビゲーション">
        {items.map(item => {
          const Icon = item.icon
          return <button key={item.id} className={page === item.id ? 'active' : ''} onClick={() => onNavigate(item.id)}>
            <Icon size={19} /><span>{item.label}</span>
          </button>
        })}
      </nav>
      <div className="sidebar-foot"><PanelLeftClose size={16} /> localhost only</div>
    </aside>
    <main className="main-content">{children}</main>
  </div>
}

