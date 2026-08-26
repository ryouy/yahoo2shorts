import type { ReactNode } from 'react'

export default function EmptyState({ icon, title, description, action }: { icon: ReactNode; title: string; description: string; action?: ReactNode }) {
  return <div className="empty-state"><span>{icon}</span><h3>{title}</h3><p>{description}</p>{action}</div>
}

