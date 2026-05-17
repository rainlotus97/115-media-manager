import type {
  CheckCookieResponse,
  CookieStatusResponse,
  CookieSaveResponse,
  ShareInfoResponse,
  SaveResponse,
  ShareInfoRequest,
  SaveRequest,
  AuthResponse,
  TMDBSearchResponse,
  TMDBDetailResponse,
  TMDBSeriesResponse,
  TMDBConfigResponse,
  WatchlistListResponse,
  WatchlistDetailResponse,
  WatchlistMutationResponse,
  AddWatchlistRequest,
} from './types'

async function post<T>(path: string, body?: unknown, token?: string): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (token) headers['Authorization'] = `Bearer ${token}`
  const res = await fetch(path, {
    method: 'POST',
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json() as Promise<T>
}

async function get<T>(path: string, token?: string): Promise<T> {
  const headers: Record<string, string> = {}
  if (token) headers['Authorization'] = `Bearer ${token}`
  const res = await fetch(path, { headers })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json() as Promise<T>
}

function getToken(): string | undefined {
  return localStorage.getItem('token') || undefined
}

async function put<T>(path: string, body?: unknown, token?: string): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (token) headers['Authorization'] = `Bearer ${token}`
  const res = await fetch(path, {
    method: 'PUT',
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json() as Promise<T>
}

async function del<T>(path: string, token?: string): Promise<T> {
  const headers: Record<string, string> = {}
  if (token) headers['Authorization'] = `Bearer ${token}`
  const res = await fetch(path, { method: 'DELETE', headers })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json() as Promise<T>
}

// Existing 115 APIs
export const api = {
  checkCookie: () =>
    post<CheckCookieResponse>('/api/check-cookie'),

  getCookieStatus: () =>
    post<CookieStatusResponse>('/api/cookie'),

  saveCookie: (cookie: string) =>
    post<CookieSaveResponse>('/api/cookie', { cookie }),

  getShareInfo: (params: ShareInfoRequest) =>
    post<ShareInfoResponse>('/api/info', params),

  saveFiles: (params: SaveRequest) =>
    post<SaveResponse>('/api/save', params),

  // Auth APIs
  register: (username: string, password: string) =>
    post<AuthResponse>('/api/auth/register', { username, password }),

  login: (username: string, password: string) =>
    post<AuthResponse>('/api/auth/login', { username, password }),

  getSession: () =>
    get<AuthResponse>('/api/auth/session', getToken()),

  logout: () =>
    post<{ ok: boolean }>('/api/auth/logout', {}, getToken()),

  // TMDB APIs
  getTMDBConfig: () =>
    get<TMDBConfigResponse>('/api/tmdb/config'),

  setTMDBConfig: (apiKey: string) =>
    post<{ ok: boolean }>('/api/tmdb/config', { api_key: apiKey }),

  searchTMDB: (query: string, mediaType: string = 'tv', page: number = 1) =>
    get<TMDBSearchResponse>(
      `/api/tmdb/search?query=${encodeURIComponent(query)}&type=${mediaType}&page=${page}`
    ),

  getTMDBDetail: (tmdbId: number, mediaType: string = 'tv') =>
    get<TMDBDetailResponse>(`/api/tmdb/${tmdbId}?type=${mediaType}`),

  getTMDBSeason: (tmdbId: number, seasonNumber: number) =>
    get<TMDBSeriesResponse>(`/api/tmdb/${tmdbId}/season/${seasonNumber}`),

  // Media / Watchlist APIs
  getWatchlist: (type?: string, region?: string, status?: string) => {
    const params = new URLSearchParams()
    if (type) params.set('type', type)
    if (region) params.set('region', region)
    if (status) params.set('status', status)
    const qs = params.toString()
    return get<WatchlistListResponse>(`/api/media/list${qs ? '?' + qs : ''}`, getToken())
  },

  addWatchlist: (data: AddWatchlistRequest) =>
    post<WatchlistMutationResponse>('/api/media/add', data, getToken()),

  getWatchlistDetail: (id: number) =>
    get<WatchlistDetailResponse>(`/api/media/${id}`, getToken()),

  updateWatchlist: (id: number, data: Partial<AddWatchlistRequest>) =>
    put<WatchlistMutationResponse>(`/api/media/${id}`, data, getToken()),

  deleteWatchlist: (id: number) =>
    del<WatchlistMutationResponse>(`/api/media/${id}`, getToken()),

  syncWatchlist: (id: number) =>
    post<any>(`/api/media/${id}/sync`, {}, getToken()),

  getMediaEpisodes: (id: number, season?: number) =>
    get<any>(`/api/media/${id}/episodes${season ? '?season=' + season : ''}`, getToken()),

  // Download APIs
  addCloudDownload: (magnetUrl: string, targetPath?: string) =>
    post<{ ok: boolean; task_id?: string; error?: string }>(
      '/api/download/cloud',
      { magnet_url: magnetUrl, target_path: targetPath },
      getToken()
    ),

  getDownloadTasks: (page?: number) =>
    get<any>(`/api/download/tasks${page ? '?page=' + page : ''}`, getToken()),
}
