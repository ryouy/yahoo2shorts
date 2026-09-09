export type Status =
  | 'created' | 'searching_articles' | 'waiting_article_approval' | 'fetching_content'
  | 'generating_scripts' | 'waiting_script_approval' | 'ready_for_video'
  | 'generating_video' | 'completed' | 'partial_error' | 'error'

export interface Post {
  text: string
  reply_to: number | null
  tone: string
  importance: number
  source_comment_ids: string[]
}

export interface ScriptContent {
  title: string
  source: string
  url: string
  youtube_title?: string
  youtube_hashtags?: string[]
  youtube_summary?: string
  intro: { headline: string; explainer: string; narration: string; summary_narration?: string }
  posts: Post[]
  outro: { text: string; narration: string }
  estimated_seconds?: number
}

export interface ScriptRecord {
  article_id: number
  approved: number
  estimated_seconds: number
  content: ScriptContent
}

export interface Article {
  id: number
  project_id: string
  url: string
  title: string
  source: string
  published_at?: string
  age_hours?: number
  comment_count: number
  ai_score: number
  comment_score: number
  freshness_score: number
  combined_score: number
  reason: string
  discovery_source: string
  selected: number
  status: string
  error?: string
  video_duration?: number
  video_path?: string
  thumbnail_path?: string
  bgm_track?: string | null
  script?: ScriptRecord
}

export interface Job {
  id: string
  project_id: string
  article_id?: number
  kind: string
  status: 'queued' | 'running' | 'cancelling' | 'cancelled' | 'completed' | 'error'
  progress: number
  stage: string
  error?: string
  logs: { at: string; message: string }[]
}

export interface Project {
  id: string
  status: Status
  request_mode: string
  request_text: string
  article_count: number
  video_mode: 'normal' | 'gold'
  created_at: string
  updated_at: string
  error?: string
  articles: Article[]
  jobs: Job[]
}

export interface ProjectSummary extends Omit<Project, 'articles' | 'jobs'> {
  article_total: number
  success_count: number
  error_count: number
}

