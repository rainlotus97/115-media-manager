// ---- API Response Types ----

export interface CheckCookieResponse {
  ok: boolean
  error?: string
}

export interface CookieStatusResponse {
  ok: boolean
  has_cookie?: boolean
}

export interface CookieSaveResponse {
  ok: boolean
  error?: string
}

export interface FileItem {
  name: string
  is_dir: boolean
  size: number
}

export interface ShareInfoResponse {
  ok: boolean
  share_code?: string
  title?: string
  file_count?: number
  size?: number
  size_str?: string
  files?: FileItem[]
  file_id_map?: Record<string, string>
  browse_cid?: string
  is_expired?: boolean
  user_name?: string
  error?: string
  hint?: string
}

export interface SaveResponse {
  ok: boolean
  target_path?: string
  error?: string
}

// ---- Request Payloads ----

export interface ShareInfoRequest {
  url?: string
  password?: string
  cid?: string
}

export interface SaveRequest {
  url: string
  password: string
  target_path: string
  file_ids?: string
}

// ---- Auth Types ----

export interface AuthResponse {
  ok: boolean
  token?: string
  user?: UserInfo
  error?: string
}

export interface UserInfo {
  id: number
  username: string
}

// ---- Internal State Types ----

export interface Breadcrumb {
  name: string
  cid: string
}

export type ToastType = 'success' | 'error' | 'info'

export interface Toast {
  id: number
  message: string
  type: ToastType
}

// ---- UI State ----

export type ActivePage =
  | 'dashboard'
  | 'anime'
  | 'movies'
  | 'tv'
  | 'share-link'
  | 'cloud-download'
  | 'direct-link'
  | 'settings'

// ---- TMDB Types ----

export interface TMDBSearchItem {
  tmdb_id: number
  title: string
  original_title: string
  year: string
  overview: string
  poster_url: string | null
  backdrop_url: string | null
  media_type: string
  vote_average: number
}

export interface TMDBSearchResponse {
  ok: boolean
  items?: TMDBSearchItem[]
  total_results?: number
  page?: number
  total_pages?: number
  error?: string
}

export interface TMDBSeason {
  season_number: number
  name: string
  episode_count: number
  poster_path: string | null
}

export interface TMDBDetailResponse {
  ok: boolean
  tmdb_id?: number
  title?: string
  original_title?: string
  year?: string
  overview?: string
  poster_url?: string | null
  backdrop_url?: string | null
  genres?: string[]
  region?: string
  vote_average?: number
  total_episodes?: number
  number_of_seasons?: number
  seasons?: TMDBSeason[]
  status?: string
  error?: string
}

export interface TMDBSeriesEpisode {
  episode_number: number
  name: string
  overview: string
  still_url: string | null
  air_date: string
}

export interface TMDBSeriesResponse {
  ok: boolean
  season_number?: number
  name?: string
  episodes?: TMDBSeriesEpisode[]
  error?: string
}

export interface TMDBConfigResponse {
  configured: boolean
  enabled: boolean
}

// ---- Media / Watchlist Types ----

export interface WatchlistItem {
  id: number
  user_id: number
  tmdb_id: number | null
  title: string
  original_title: string
  media_type: 'anime' | 'movie' | 'tv'
  region: string
  genre: string
  poster_path: string
  backdrop_path: string
  overview: string
  total_episodes: number
  cached_episodes: number
  latest_episode: number
  status: 'tracking' | 'completed' | 'paused'
  path_115: string
  folder_id_115: string
  last_synced_at: string
  next_sync_at: string
  auto_sync_days: string
  created_at: string
  updated_at: string
  cached_files?: CachedFile[]
}

export interface CachedFile {
  id: number
  fid: string
  filename: string
  file_size: number
  episode_number: number
  season_number: number
}

export interface WatchlistDetailResponse {
  ok: boolean
  item?: WatchlistItem
  error?: string
}

export interface WatchlistListResponse {
  ok: boolean
  items: WatchlistItem[]
}

export interface AddWatchlistRequest {
  tmdb_id?: number
  title: string
  original_title?: string
  media_type: string
  region?: string
  genres?: string[]
  poster_url?: string
  backdrop_url?: string
  overview?: string
  total_episodes?: number
  status?: string
  path_115?: string
}

export interface WatchlistMutationResponse {
  ok: boolean
  id?: number
  error?: string
}
