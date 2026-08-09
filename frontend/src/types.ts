export type ActivePage = 'library' | 'import' | 'cloud-download' | 'settings'

export type ToastType = 'success' | 'error' | 'info'

export interface Toast {
  id: number
  message: string
  type: ToastType
}

export interface PanSession {
  ok: boolean
  cached?: boolean
  error?: string
  requires_verification?: boolean
  verification_url?: string
}

export interface Resource {
  id: number
  title: string
  match_key: string
  path_115: string
  folder_id_115: string | null
  tmdb_id: number | null
  media_type: string
  poster_url: string
  overview: string
  total_episodes: number
  cached_episodes: number
  latest_episode: number
  seasons_json: string
  replace_rules_json?: string
  file_count: number
  total_size: number
  last_synced_at: string
  created_at: string
  updated_at: string
}

export interface ResourceFile {
  id?: number
  fid: string
  name: string
  filename?: string
  size: number
  file_size?: number
  is_dir?: boolean
  display_name?: string
  season_number?: number | null
  episode_number?: number | null
  tmdb_valid?: number
}

export interface ResourceDetail {
  ok: boolean
  item: Resource
  files: ResourceFile[]
}

export interface ImportMatch {
  resource_id: number
  title: string
  path_115: string
  matched_file_ids: string[]
}

export interface ImportPreview {
  ok: boolean
  title: string
  share_code: string
  files: ResourceFile[]
  matches: ImportMatch[]
  error?: string
}

export interface ReceiveRecord {
  id: string
  name: string
  parent_name: string
  file_size: number
  create_time: number
  update_time?: number
}

export interface PanDirItem {
  fid: string
  name: string
  size: number
  is_dir: boolean
}

export interface PanDir {
  ok: boolean
  cid: string
  items: PanDirItem[]
  error?: string
}

export interface TmdbSearchItem {
  tmdb_id: number
  title: string
  original_title: string
  year: string
  overview: string
  poster_url: string
  backdrop_url: string
  media_type: string
  vote_average: number
}

export interface TmdbSearchResult {
  ok: boolean
  items: TmdbSearchItem[]
  total_results: number
  error?: string
}

export interface TmdbSeason {
  season_number: number
  name: string
  episode_count: number
  poster_path: string | null
}

export interface TmdbDetail {
  ok: boolean
  tmdb_id: number
  media_type: string
  title: string
  original_title: string
  year: string
  overview: string
  poster_url: string
  backdrop_url: string
  total_episodes: number
  number_of_seasons: number
  seasons: TmdbSeason[]
  status: string
  error?: string
}

export interface ResourceSyncResult {
  ok: boolean
  files: number
  episodes_cached: number
  total_episodes: number
  seasons: number[]
  seasons_json: string
  truncated: boolean
  error?: string
}

export interface QrLogin {
  ok: boolean
  uid?: string
  qr_url?: string
  expires_in?: number
  error?: string
}

export interface QrLoginStatus {
  ok: boolean
  status: 'waiting' | 'scanned' | 'confirmed' | 'authorized' | 'expired' | 'canceled' | 'error'
  error?: string
}

export interface DownloadTask {
  task_id: string
  name?: string
  status: number
  percent?: number
  size?: string
}

export interface RenamePreviewItem {
  fid: string
  name: string
  new_name: string | null
  current_prefix?: string | null
  same_prefix?: boolean
  no_episode?: boolean
  will_rename: boolean
}

export interface RenameTarget {
  fid: string
  old_name: string
  new_name: string
}

export interface TaskStatus {
  ok: boolean
  done: boolean
  stage: string
  current: number
  total: number
  error?: string | null
  result?: {
    item?: Resource
    sync?: ResourceSyncResult
    index_truncated?: boolean
    renamed?: number
    skipped?: number
    skipped_samples?: string[]
    errors?: string[]
    synced?: number
  } | null
}
