import type { ReactNode } from 'react'
import { FilePlus2, Gauge, Settings } from 'lucide-react'

export type Page = 'dashboard' | 'new' | 'settings' | 'project'

interface Props {
  page: Page
  onNavigate: (page: Page) => void
  children: ReactNode
}

const items: { id: Page; label: string; icon: typeof Gauge }[] = [
  { id: 'dashboard', label: 'ダッシュボード', icon: Gauge },
  { id: 'new', label: '新規作成', icon: FilePlus2 },
  { id: 'settings', label: '設定', icon: Settings },
]

export default function Shell({ page, onNavigate, children }: Props) {
  return <div className="app-shell">
    <aside className="sidebar">
      <button className="brand" onClick={() => onNavigate('dashboard')}>
        <b>yc2ys</b>
      </button>
      <nav aria-label="メインナビゲーション">
        {items.map(item => {
          const Icon = item.icon
          return <button key={item.id} className={page === item.id ? 'active' : ''} onClick={() => onNavigate(item.id)}>
            <Icon size={19} /><span>{item.label}</span>
          </button>
        })}
      </nav>
    </aside>
    <main className="main-content">{children}</main>
  </div>
}
