import { ArrowLeft, ExternalLink, Newspaper } from 'lucide-react'
import { useEffect, useState } from 'react'
import { api } from '../api'
import EmptyState from '../components/EmptyState'

interface UsedArticle { url: string; title: string; project_id: string; article_id: number; created_at: string }
interface Props { onBack: () => void; onError: (value: string) => void }

export default function UsedArticles({ onBack, onError }: Props) {
  const [articles, setArticles] = useState<UsedArticle[] | null>(null)

  useEffect(() => {
    api.get<{ articles: UsedArticle[] }>('/used-articles').then(v => setArticles(v.articles)).catch(e => onError(e instanceof Error ? e.message : String(e)))
  }, [])

  return <>
    <header className="page-head compact-head">
      <div><button className="back-button" onClick={onBack}><ArrowLeft size={17} /> ダッシュボードへ</button><h1>使用済み記事一覧</h1><p>動画生成まで完了した記事です。テーマ検索・Gold検索では自動的に除外されます。</p></div>
    </header>
    {articles === null ? <div className="loading">読み込み中…</div> :
      articles.length === 0 ? <EmptyState icon={<Newspaper />} title="まだありません" /> :
      <section className="section-card">
        <div className="used-articles-list">{articles.map(item => <div className="used-article-row" key={item.url}>
          <div><b>{item.title || item.url}</b><small>{new Date(item.created_at).toLocaleString('ja-JP')}</small></div>
          <a href={item.url} target="_blank" rel="noreferrer">開く <ExternalLink size={14} /></a>
        </div>)}</div>
      </section>}
  </>
}
