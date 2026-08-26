const labels: Record<string, string> = {
  created: '作成済み', searching_articles: '記事を探索中', waiting_article_approval: '記事選択待ち',
  fetching_content: '本文・コメント取得中', generating_scripts: '原稿生成中', waiting_script_approval: '原稿確認待ち',
  ready_for_video: '動画生成可能', generating_video: '動画生成中', completed: '完了', partial_error: '一部エラー',
  error: 'エラー', candidate: '候補', approved: '承認済み', waiting_script: '原稿待ち',
}

export default function StatusBadge({ status }: { status: string }) {
  const kind = status.includes('error') ? 'danger' : status === 'completed' ? 'success' : status.includes('waiting') || status === 'ready_for_video' ? 'warning' : 'neutral'
  return <span className={`status ${kind}`}><i />{labels[status] || status}</span>
}

