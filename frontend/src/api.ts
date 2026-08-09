import type {
  ImportPreview, PanDir, PanSession, Resource, ResourceDetail, ResourceFile,
  ResourceSyncResult, TmdbDetail, TmdbSearchResult, QrLogin, QrLoginStatus, DownloadTask, ReceiveRecord,
  RenamePreviewItem, RenameTarget, TaskStatus,
} from './types'
import { directApi } from './directApi'
import { useSessionEvents } from './composables/useSessionEvents'

const GATEWAY_KEY = 'pan115-gateway-url'

function gatewayUrl() {
  return localStorage.getItem(GATEWAY_KEY)?.replace(/\/$/, '') || import.meta.env.VITE_API_BASE?.replace(/\/$/, '') || ''
}

async function request<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${gatewayUrl()}${path}`, {
      method,
      headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch {
    throw new Error('无法连接后端服务，请确认 115-server.py 已启动')
  }
  let data: { error?: string } & T
  try {
    data = await response.json() as { error?: string } & T
  } catch {
    data = { error: `后端返回异常（HTTP ${response.status}）` } as { error?: string } & T
  }
  if (response.status === 401 && !path.startsWith('/api/pan/session')) {
    useSessionEvents().trigger()
  }
  if (!response.ok) throw Object.assign(new Error((data as { error?: string }).error || `HTTP ${response.status}`), { data })
  return data
}

export function getGatewayUrl() { return gatewayUrl() }
export function setGatewayUrl(value: string) {
  const clean = value.trim().replace(/\/$/, '')
  if (clean) localStorage.setItem(GATEWAY_KEY, clean)
  else localStorage.removeItem(GATEWAY_KEY)
}

const serverApi = {
  getSession: () => request<PanSession>('/api/pan/session'),
  login: (account: string, password: string) => request<PanSession>('/api/pan/login', 'POST', { account, password }),
  logout: () => request<{ ok: boolean }>('/api/pan/session', 'DELETE'),
  createQrLogin: () => request<QrLogin>('/api/pan/qrcode', 'POST'),
  getQrLoginStatus: (uid: string) => request<QrLoginStatus>(`/api/pan/qrcode/${encodeURIComponent(uid)}`),
  cancelQrLogin: (uid: string) => request<{ ok: boolean }>(`/api/pan/qrcode/${encodeURIComponent(uid)}`, 'DELETE'),

  browsePanDir: (cid: string) => request<PanDir>(`/api/pan/dir?cid=${encodeURIComponent(cid || '0')}`),
  getReceiveHistory: () => request<{ ok: boolean; total?: number; records?: ReceiveRecord[] }>('/api/pan/receive-history'),
  clearReceiveHistory: (ids: string[]) => request<{ ok: boolean; deleted?: number }>('/api/pan/receive-history/clear', 'POST', { ids }),
  getResources: (query = '') => request<{ ok: boolean; items: Resource[] }>(`/api/resources${query ? `?q=${encodeURIComponent(query)}` : ''}`),
  syncAllResources: () => request<{ ok: boolean; task_id?: string; result?: { synced?: number; errors?: string[] }; error?: string }>('/api/resources/sync-all', 'POST'),
  getResource: (id: number) => request<ResourceDetail>(`/api/resources/${id}`),
  deleteResource: (id: number) => request<{ ok: boolean }>(`/api/resources/${id}`, 'DELETE'),
  previewImport: (url: string, password: string) =>
    request<ImportPreview>('/api/resources/preview', 'POST', { url, password }),
  importFiles: (payload: {
    url: string; password: string; title: string; target_path?: string; resource_id?: number; file_ids: string[]; files: ResourceFile[]
  }) => request<{ ok: boolean; resource_id?: number; target_path?: string; error?: string }>('/api/resources/import', 'POST', payload),
  addResourceFolder: (payload: {
    path_115: string; title?: string; tmdb_id?: number | null; media_type?: string;
    poster_url?: string; overview?: string; total_episodes?: number
  }) => request<{ ok: boolean; task_id?: string; item?: Resource; items?: Resource[]; sync?: ResourceSyncResult; index_truncated?: boolean; error?: string }>(
    '/api/resources/folder', 'POST', payload),
  getTaskStatus: (taskId: string) => request<TaskStatus>(`/api/tasks/${encodeURIComponent(taskId)}`),
  syncResource: (id: number) => request<{ ok: boolean; item: Resource; stats: ResourceSyncResult }>(`/api/resources/${id}/sync`, 'POST'),
  refreshTmdb: (id: number) => request<{ ok: boolean; item: Resource }>(`/api/resources/${id}/tmdb-refresh`, 'POST'),
  renamePreview: (id: number, prefix: string) =>
    request<{ ok: boolean; prefix?: string; suggested_prefix?: string | null; total?: number; parsed?: number; items?: RenamePreviewItem[] }>(
      `/api/resources/${id}/rename-preview`, 'POST', { prefix }),
  renameResourceFile: (id: number, fid: string, newName: string) =>
    request<{ ok: boolean; file?: ResourceFile }>(`/api/resources/${id}/rename-file`, 'POST', { fid, new_name: newName }),
  renameResourceFiles: (id: number, prefix: string, options?: { renames?: RenameTarget[]; concurrency?: number; interval_ms?: number }) =>
    request<{ ok: boolean; task_id?: string; result?: { renamed?: number; skipped?: number; skipped_samples?: string[]; errors?: string[]; item?: Resource }; error?: string }>(
      `/api/resources/${id}/rename-files`, 'POST', { prefix, ...options }),
  updateResourceTitle: (id: number, title: string) => request<{ ok: boolean; item: Resource }>(`/api/resources/${id}/title`, 'POST', { title }),
  attachTmdb: (id: number, payload: {
    tmdb_id: number; media_type?: string; title?: string; poster_url?: string; overview?: string; total_episodes?: number
  }) => request<{ ok: boolean; item: Resource; stats: ResourceSyncResult }>(`/api/resources/${id}/tmdb`, 'POST', payload),

  getTmdbConfig: () => request<{ configured: boolean; enabled: boolean }>('/api/tmdb/config'),
  setTmdbConfig: (apiKey: string) => request<{ ok: boolean }>('/api/tmdb/config', 'POST', { api_key: apiKey }),
  posterProxyUrl: (url: string) => `${gatewayUrl()}/api/tmdb/image?url=${encodeURIComponent(url)}`,
  searchTmdb: (query: string, mediaType = 'tv') => request<TmdbSearchResult>(`/api/tmdb/search?query=${encodeURIComponent(query)}&type=${encodeURIComponent(mediaType)}`),
  getTmdbDetail: (id: number, mediaType = 'tv') => request<TmdbDetail>(`/api/tmdb/${id}?type=${encodeURIComponent(mediaType)}`),

  addCloudDownload: (magnetUrl: string, targetPath?: string) => request<{ ok: boolean; task_id?: string; error?: string }>(
    '/api/download/cloud', 'POST', { magnet_url: magnetUrl, target_path: targetPath }),
  getDownloadTasks: (page?: number) => request<{ state?: boolean; tasks?: DownloadTask[] }>(`/api/download/tasks${page ? `?page=${page}` : ''}`),
}

const isNative =
  typeof window !== 'undefined' &&
  typeof (window as any).Capacitor?.isNativePlatform === 'function' &&
  (window as any).Capacitor.isNativePlatform()

export const api = isNative ? directApi : serverApi
export const isNativePlatform = isNative
export type { DownloadTask, QrLogin, QrLoginStatus }
