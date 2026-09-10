import type { ReactNode } from 'react'
import { ExternalLink, FilePlus2, Gauge, Settings } from 'lucide-react'

export type Page = 'dashboard' | 'new' | 'settings' | 'project' | 'used-articles'

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
  const isDesktop = navigator.userAgent.includes('Electron')
  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand">
        <b>yc2ys</b>
      </div>
      <nav aria-label="メインナビゲーション">
        {items.map(item => {
          const Icon = item.icon
          return <button key={item.id} className={page === item.id ? 'active' : ''} onClick={() => onNavigate(item.id)}>
            <Icon size={19} /><span>{item.label}</span>
          </button>
        })}
      </nav>
    </aside>
    <main className="main-content">
      {isDesktop && <div className="desktop-toolbar"><span>ローカルサーバーで動作中</span><button className="desktop-browser-button" onClick={() => window.open(window.location.href, '_blank', 'noopener')}>ブラウザで開く <ExternalLink size={15} /></button></div>}
      {children}
    </main>
  </div>
}
