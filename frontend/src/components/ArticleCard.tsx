import { Check, ExternalLink, MessageCircle, Sparkles } from 'lucide-react'
import type { Article } from '../types'

export default function ArticleCard({ article, checked, onToggle }: { article: Article; checked: boolean; onToggle: () => void }) {
  return <article className={`article-card ${checked ? 'selected' : ''}`}>
    <button className={`check-box ${checked ? 'checked' : ''}`} onClick={onToggle} aria-label={checked ? '選択解除' : '選択'}>{checked && <Check size={17} />}</button>
    <div className="article-main">
      <div className="article-meta"><span>{article.source || 'Yahoo!ニュース'}</span><i />{article.age_hours == null ? '日時不明' : `${article.age_hours}時間前`}<i /><MessageCircle size={14} /> {article.comment_count}件</div>
      <h3>{article.title || 'タイトル取得中'}</h3>
      <p className="reason"><Sparkles size={15} /> <span><b>AIの選定理由</b>{article.reason || '指定記事'}</span></p>
      <a href={article.url} target="_blank" rel="noreferrer">Yahooで開く <ExternalLink size={14} /></a>
    </div>
    <div className="score-box"><small>総合 SCORE</small><strong>{Number(article.combined_score || 0).toFixed(1)}</strong>
      <dl><div><dt>AI適合度</dt><dd>{article.ai_score}</dd></div><div><dt>コメント</dt><dd>{Math.round(article.comment_score)}</dd></div><div><dt>新しさ</dt><dd>{Math.round(article.freshness_score)}</dd></div></dl>
      <span className="source-tag">{article.discovery_source}</span>
    </div>
  </article>
}

