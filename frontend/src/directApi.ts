import { CapacitorCookies, CapacitorHttp } from '@capacitor/core'
import { useResourceCache } from './composables/useResourceCache'
import type {
  DownloadTask, ImportMatch, ImportPreview, PanDir, PanDirItem, PanSession,
  QrLogin, QrLoginStatus, ReceiveRecord, Resource, ResourceDetail, ResourceFile,
  ResourceSyncResult, TmdbDetail, TmdbSearchItem, TmdbSearchResult,
} from './types'

const UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1'
const BASE_HEADERS: Record<string, string> = {
  'User-Agent': UA,
  'Accept': 'application/json, text/javascript, */*; q=0.01',
}
const QR_BASES = [
  'https://qrcodeapi.115.com',
  'https://hnqrcodeapi.115.com',
  'https://passportapi.115.com',
  'https://hnpassportapi.115.com',
]
const SESSION_KEY = 'pan115-native-session'
const TMDB_KEY = 'pan115-tmdb-key'
const cache = useResourceCache()
const qrTokens = new Map<string, { time: string; sign: string; base: string }>()

function isObject(value: unknown): value is Record<string, any> {
  return typeof value === 'object' && value !== null
}
function serializeCookie(cookie: unknown): string {
  if (isObject(cookie)) {
    return Object.entries(cookie)
      .filter(([, v]) => v !== undefined && v !== null && v !== '')
      .map(([k, v]) => `${String(k).toUpperCase()}=${v}`)
      .join('; ')
  }
  return String(cookie || '').trim()
}

async function nativeRequest(
  url: string,
  options: {
    method?: string
    headers?: Record<string, string>
    params?: Record<string, string | number>
    form?: Record<string, string | number>
    data?: unknown
  } = {},
) {
  const headers: Record<string, string> = { ...BASE_HEADERS, ...(options.headers || {}) }
  let data: unknown = options.data
  if (options.form) {
    headers['Content-Type'] = 'application/x-www-form-urlencoded; charset=UTF-8'
    data = new URLSearchParams(Object.entries(options.form).map(([k, v]) => [k, String(v)])).toString()
  }
  const response = await CapacitorHttp.request({
    url,
    method: (options.method || 'GET') as any,
    headers,
    params: options.params || undefined,
    data: data as any,
  } as any)
  return {
    status: response.status,
    data: response.data,
    headers: response.headers,
  }
}

async function getSessionCookie(): Promise<string> {
  return localStorage.getItem(SESSION_KEY) || ''
}
async function setSessionCookies(cookie: string) {
  localStorage.setItem(SESSION_KEY, cookie)
  const urls = ['https://115.com', 'https://webapi.115.com', 'https://115cdn.com']
  for (const pair of cookie.split(';')) {
    const eq = pair.indexOf('=')
    if (eq <= 0) continue
    const key = pair.slice(0, eq).trim()
    const value = pair.slice(eq + 1).trim()
    for (const url of urls) {
      try { await CapacitorCookies.setCookie({ url, key, value }) } catch { /* ignore */ }
    }
  }
}
async function clearSessionCookies() {
  localStorage.removeItem(SESSION_KEY)
  for (const url of ['https://115.com', 'https://webapi.115.com', 'https://115cdn.com']) {
    try { await CapacitorCookies.clearCookies({ url }) } catch { /* ignore */ }
  }
}

async function checkCookie(): Promise<boolean> {
  const cookie = await getSessionCookie()
  if (!cookie) return false
  try {
    const res = await nativeRequest('https://webapi.115.com/user/info')
    const body = res.data
    return Boolean(body?.state ?? (isObject(body) && isObject(body.data) ? body.data.state : false))
  } catch {
    return false
  }
}

async function listDir(cid: string): Promise<PanDirItem[]> {
  const all: PanDirItem[] = []
  let offset = 0
  while (true) {
    const res = await nativeRequest('https://webapi.115.com/files', {
      params: { cid, offset, limit: 200, show_dir: 1 },
    })
    const body = res.data
    if (!body?.state) break
    const page: any[] = body.data || []
    if (!page.length) break
    for (const f of page) {
      const isDir = f.f !== undefined ? !f.f : Boolean(f.cid && !f.fid)
      all.push({
        fid: String(isDir ? f.cid : f.fid),
        name: String(f.n || '?'),
        size: Number(f.s || 0),
        is_dir: isDir,
      })
    }
    offset += 200
    if (offset >= Number(body.count || 0)) break
  }
  return all
}

async function findSubfolder(parentCid: string, name: string): Promise<string | null> {
  const items = await listDir(parentCid)
  const found = items.find(i => i.is_dir && i.name === name)
  return found?.fid || null
}
async function findCidByPath(path: string): Promise<string | null> {
  const parts = path.split('/').map(p => p.trim()).filter(Boolean)
  let cid = '0'
  for (const part of parts) {
    const found = await findSubfolder(cid, part)
    if (!found) return null
    cid = found
  }
  return cid
}
async function ensurePath(path: string): Promise<string | null> {
  const parts = path.split('/').map(p => p.trim()).filter(Boolean)
  let cid = '0'
  for (const part of parts) {
    const found = await findSubfolder(cid, part)
    if (found) {
      cid = found
    } else {
      try {
        const res = await nativeRequest('https://webapi.115.com/files/add', {
          method: 'POST',
          form: { pid: cid, cname: part },
        })
        const body = res.data
        cid = String(body?.cid || body?.file_id || '')
        if (!cid) return null
      } catch {
        return null
      }
    }
  }
  return cid
}

async function listTreeFiles(cid: string): Promise<{ files: ResourceFile[]; truncated: boolean }> {
  const files: ResourceFile[] = []
  const pending = [cid]
  const maxFiles = 20000
  while (pending.length && files.length < maxFiles) {
    const current = pending.shift()!
    const items = await listDir(current)
    for (const item of items) {
      if (files.length >= maxFiles) return { files, truncated: true }
      if (item.is_dir) pending.push(item.fid)
      else files.push({ fid: item.fid, name: item.name, size: item.size, is_dir: false })
    }
  }
  return { files, truncated: files.length >= maxFiles }
}

function parseEpisode(filename: string): { season: number; episode: number } | null {
  const name = filename.trim()
  let m = /[sS](\d{1,2})\s*[eE](\d{1,4})/.exec(name)
  if (m) return { season: Number(m[1]), episode: Number(m[2]) }
  m = /(?:^|[^a-zA-Z])[eE][pP]\.?\s*(\d{1,4})/.exec(name)
  if (m) return { season: 1, episode: Number(m[1]) }
  m = /\[(\d{1,4}(?:\.5)?)\]/.exec(name)
  if (m) return { season: 1, episode: Math.floor(Number(m[1])) }
  m = /第\s*(\d{1,4})\s*(?:集|话|話)/.exec(name)
  if (m) return { season: 1, episode: Number(m[1]) }
  const stem = name.replace(/\.[^.]+$/, '')
  m = /(?:^|\s)(\d{1,4}(?:\.5)?)(?:\s|$)/.exec(stem)
  if (m) {
    const ep = Math.floor(Number(m[1]))
    if (ep >= 1 && ep <= 9999) return { season: 1, episode: ep }
  }
  return null
}
function parseSeasonFromDirname(dirname: string): number | null {
  const name = dirname.trim()
  let m = /[Ss]eason\s*\.?\s*(\d{1,2})/.exec(name)
  if (m) return Number(m[1])
  m = /(?:^|\s)[Ss](\d{1,2})(?:\s|$)/.exec(name)
  if (m) return Number(m[1])
  m = /第\s*(\d{1,2})\s*季/.exec(name)
  if (m) return Number(m[1])
  m = /[Ss]eason\.?(\d{1,2})/.exec(name)
  if (m) return Number(m[1])
  return null
}
function matchKey(value: string): string {
  return value
    .replace(/\.[^.]+$/, '')
    .toLowerCase()
    .replace(/(s\d{1,2}\s*e\d{1,4}|ep?\s*\d{1,4}|第\s*\d{1,4}\s*[集话話])/g, ' ')
    .replace(/[\[\](){}._\-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, 160)
}

function buildPatternName(prefix: string, name: string): string | null {
  const cleanPrefix = (prefix || '').trim().replace(/\s+\.+$/, '')
  if (!cleanPrefix) return null
  const parsed = parseEpisode(name)
  if (!parsed) return null
  const dot = name.lastIndexOf('.')
  const ext = dot >= 0 ? name.slice(dot + 1) : ''
  if (!ext) return null
  const season = Math.max(1, parsed.season || 1)
  const episode = parsed.episode || 0
  if (episode <= 0) return null
  return `${cleanPrefix}.S${String(season).padStart(2, '0')}E${String(episode).padStart(2, '0')}.${ext}`
}
function episodePrefix(name: string): string | null {
  const m = /[sS]\d{1,2}\s*[eE]\d{1,4}/.exec(name || '')
  if (!m) return null
  return (name || '').slice(0, m.index).replace(/[\s._-]+$/, '')
}
function normalizePrefix(value?: string | null): string {
  return String(value || '')
    .trim()
    .toLowerCase()
    .normalize('NFKC')
    .replace(/[\s._\-:：·,，、()\[\]【】{}]+/g, '')
}
function prefixesMatch(a?: string | null, b?: string | null): boolean {
  return normalizePrefix(a) === normalizePrefix(b)
}
async function scanResourceFolder(cid: string): Promise<{ files: ResourceFile[]; episodes: Record<number, Set<number>>; truncated: boolean }> {
  const files: ResourceFile[] = []
  const episodes: Record<number, Set<number>> = {}
  const pending: { cid: string; season: number }[] = [{ cid, season: 1 }]
  const maxFiles = 20000
  let truncated = false
  while (pending.length && files.length < maxFiles) {
    const { cid: current, season: seasonContext } = pending.shift()!
    const items = await listDir(current)
    for (const item of items) {
      if (files.length >= maxFiles) { truncated = true; break }
      if (item.is_dir) {
        let season = parseSeasonFromDirname(item.name)
        if (season === null && /^\d{1,2}$/.test(item.name.trim())) season = Number(item.name.trim())
        pending.push({ cid: item.fid, season: season ?? seasonContext })
      } else {
        const displayName = item.name
        const parsed = parseEpisode(displayName)
        files.push({
          fid: item.fid,
          name: item.name,
          size: item.size,
          is_dir: false,
          display_name: displayName,
          season_number: parsed?.season ?? null,
          episode_number: parsed?.episode ?? null,
        })
        if (parsed) {
          episodes[parsed.season] = episodes[parsed.season] || new Set()
          episodes[parsed.season].add(parsed.episode)
        }
      }
    }
  }
  return { files, episodes, truncated }
}

async function readResources(): Promise<Resource[]> {
  return (await cache.read()) || []
}
async function writeResources(items: Resource[]) {
  await cache.write(items)
}
function nowIso() {
  return new Date().toISOString()
}
function buildResource(data: Partial<Resource> & { title: string; path_115: string }, files: ResourceFile[], id: number): Resource {
  return {
    id,
    title: data.title,
    match_key: matchKey(data.title),
    path_115: data.path_115,
    folder_id_115: data.folder_id_115 || null,
    tmdb_id: data.tmdb_id ?? null,
    media_type: data.media_type || 'tv',
    poster_url: data.poster_url || '',
    overview: data.overview || '',
    total_episodes: Number(data.total_episodes || 0),
    cached_episodes: Number(data.cached_episodes || 0),
    latest_episode: Number(data.latest_episode || 0),
    seasons_json: data.seasons_json || '[]',
    replace_rules_json: data.replace_rules_json || '[]',
    file_count: files.length,
    total_size: files.reduce((sum, f) => sum + Number(f.size || 0), 0),
    last_synced_at: nowIso(),
    created_at: data.created_at || nowIso(),
    updated_at: nowIso(),
  }
}

async function getShareInfo(shareCode: string, receiveCode: string): Promise<{
  state: boolean
  title?: string
  file_count?: number
  size?: number
  is_expired?: boolean
  files?: ResourceFile[]
  error?: string
}> {
  try {
    const referer = `https://115cdn.com/s/${shareCode}?password=${receiveCode}&`
    const files: ResourceFile[] = []
    let totalCount = 0
    let offset = 0
    let title = ''
    let size = 0
    let isExpired = false
    while (true) {
      const res = await nativeRequest('https://115cdn.com/webapi/share/snap', {
        params: { share_code: shareCode, receive_code: receiveCode, cid: '0', limit: 200, offset, format: 'json' },
        headers: { Referer: referer },
      })
      const body = res.data
      if (!body?.state) break
      const d = body.data || {}
      if (offset === 0) {
        const info = d.shareinfo || {}
        title = String(info.share_title || '未知')
        totalCount = Number(d.count || 0)
        size = Number(info.file_size || 0)
        const expire = Number(info.expire_time || 0)
        isExpired = expire > 0 && expire * 1000 < Date.now()
      }
      const page: any[] = d.list || []
      if (!page.length) break
      for (const f of page) {
        const isDir = Number(f.fc || 0) === 0
        const fid = isDir ? String(f.cid || '') : String(f.fid || f.cid || '')
        files.push({ fid, name: String(f.n || '?'), size: Number(f.s || 0), is_dir: isDir })
      }
      offset += 200
      if (offset >= totalCount) break
    }
    return { state: true, title, file_count: totalCount, size, is_expired: isExpired, files }
  } catch (error: any) {
    return { state: false, error: String(error?.message || error) }
  }
}
async function saveFilesToPan(shareCode: string, receiveCode: string, cid: string, fileIds: string): Promise<{ ok: boolean; error?: string }> {
  try {
    const res = await nativeRequest('https://115cdn.com/webapi/share/receive', {
      method: 'POST',
      form: { share_code: shareCode, receive_code: receiveCode, cid, file_id: fileIds || '0' },
    })
    if (res.data?.state) return { ok: true }
    return { ok: false, error: String(res.data?.error || res.data?.message || '转存失败') }
  } catch (error: any) {
    return { ok: false, error: String(error?.message || error || '转存失败') }
  }
}

async function getUid(): Promise<string> {
  const cookie = await getSessionCookie()
  const m = /\bUID=([^;]+)/i.exec(cookie)
  if (m) return m[1]
  try {
    const res = await nativeRequest('https://webapi.115.com/user/info')
    const body = res.data
    if (body?.state) return String(body.data?.user_id || '')
  } catch { /* ignore */ }
  return ''
}
async function addCloudDownload(magnetUrl: string, targetPath: string) {
  const uid = await getUid()
  let sign = ''
  let signtime = ''
  try {
    const res = await nativeRequest('https://115.com/?ct=offline&ac=space')
    const body = res.data
    sign = String(body?.sign || '')
    signtime = String(body?.time || '')
  } catch { /* ignore */ }
  if (!sign) return { ok: false, error: '获取签名失败，授权可能已过期' }
  let targetCid = ''
  if (targetPath) {
    try { targetCid = (await findCidByPath(targetPath)) || '' } catch { /* ignore */ }
  }
  try {
    const res = await nativeRequest('https://115.com/web/lixian/?ct=lixian&ac=add_task_url', {
      method: 'POST',
      form: {
        url: magnetUrl,
        sign,
        time: signtime,
        ...(uid ? { uid } : {}),
        ...(targetCid ? { wp_path_id: targetCid } : {}),
      },
      headers: { Origin: 'https://115.com', Referer: 'https://115.com/' },
    })
    const body = res.data
    return {
      ok: Boolean(body?.state),
      task_id: String(body?.task_id || body?.info_hash || ''),
      error: String(body?.error || body?.message || body?.msg || ''),
    }
  } catch (error: any) {
    return { ok: false, error: String(error?.message || error) }
  }
}
async function getDownloadTasks(page: number): Promise<{ state?: boolean; tasks?: DownloadTask[]; error?: string }> {
  try {
    const res = await nativeRequest('https://115.com/web/lixian/?ct=lixian&ac=task_lists', {
      params: { page, limit: 20 },
      headers: { Referer: 'https://115.com/' },
    })
    const body = res.data
    if (!body?.state) return { state: false, error: String(body?.error || '获取失败') }
    const list: any[] = Array.isArray(body.data) ? body.data : (body.data?.list || [])
    return {
      state: true,
      tasks: list.map(t => ({
        task_id: String(t.info_hash || ''),
        name: String(t.name || ''),
        status: Number(t.status || 0),
        percent: Number(t.percent ?? t.percentDone ?? 0),
        size: String(t.size || ''),
      })),
    }
  } catch (error: any) {
    return { state: false, error: String(error?.message || error) }
  }
}

async function tmdbRequest(path: string, params: Record<string, string | number> = {}) {
  const apiKey = localStorage.getItem(TMDB_KEY) || ''
  if (!apiKey) return null
  const res = await nativeRequest(`https://api.themoviedb.org/3${path}`, {
    params: { api_key: apiKey, language: 'zh-CN', ...params },
  })
  return res.data
}

function mapTmdbItems(items: any[], mediaType: string): TmdbSearchItem[] {
  return (items || []).slice(0, 20).map((item: any) => {
    const date = String(item.first_air_date || item.release_date || '')
    return {
      tmdb_id: Number(item.id),
      title: String(item.name || item.title || '未知'),
      original_title: String(item.original_name || item.original_title || ''),
      year: date.slice(0, 4),
      overview: String(item.overview || '').slice(0, 200),
      poster_url: item.poster_path ? `https://image.tmdb.org/t/p/w342${item.poster_path}` : '',
      backdrop_url: item.backdrop_path ? `https://image.tmdb.org/t/p/w780${item.backdrop_path}` : '',
      media_type: mediaType,
      vote_average: Number(item.vote_average || 0),
    }
  })
}
function mapTmdbDetail(result: any, mediaType: string): TmdbDetail | null {
  if (!result) return null
  const seasons = (result.seasons || [])
    .filter((s: any) => Number(s.season_number || 0) > 0)
    .map((s: any) => ({
      season_number: Number(s.season_number),
      name: String(s.name || `第${s.season_number}季`),
      episode_count: Number(s.episode_count || 0),
      poster_path: s.poster_path ? `https://image.tmdb.org/t/p/w342${s.poster_path}` : null,
    }))
  const totalEpisodes = seasons.reduce((sum: number, s: any) => sum + s.episode_count, 0)
  const date = String(result.first_air_date || result.release_date || '')
  return {
    ok: true,
    tmdb_id: Number(result.id),
    title: String(result.name || result.title || '未知'),
    original_title: String(result.original_name || result.original_title || ''),
    year: date.slice(0, 4),
    overview: String(result.overview || ''),
    poster_url: result.poster_path ? `https://image.tmdb.org/t/p/w500${result.poster_path}` : '',
    backdrop_url: result.backdrop_path ? `https://image.tmdb.org/t/p/original${result.backdrop_path}` : '',
    total_episodes: totalEpisodes,
    number_of_seasons: Number(result.number_of_seasons || 1),
    seasons,
    status: String(result.status || ''),
    media_type: mediaType,
  }
}

async function fetchAiredCount(tmdbId: number, mediaType: string): Promise<number> {
  try {
    const detail = await tmdbRequest(`/${mediaType === 'movie' ? 'movie' : 'tv'}/${tmdbId}`)
    const mapped = mapTmdbDetail(detail, mediaType)
    if (!mapped) return 0
    const today = new Date().toISOString().slice(0, 10)
    let latest = 0
    for (const season of mapped.seasons) {
      const seasonResult = await tmdbRequest(`/tv/${tmdbId}/season/${season.season_number}`)
      const episodes: any[] = seasonResult?.episodes || []
      for (const ep of episodes) {
        if (ep.air_date && String(ep.air_date) <= today) {
          latest = Math.max(latest, Number(ep.episode_number || 0))
        }
      }
    }
    return latest
  } catch {
    return 0
  }
}

async function syncResourceItem(id: number): Promise<{ ok: boolean; item?: Resource; stats?: ResourceSyncResult; error?: string }> {
  const items = await readResources()
  const row = items.find(r => r.id === id)
  if (!row) return { ok: false, error: '资源不存在' }
  let cid = row.folder_id_115 || ''
  if (!cid) cid = (await findCidByPath(row.path_115)) || ''
  if (!cid) return { ok: false, error: `在 115 网盘中找不到目录: ${row.path_115}` }
  const scanned = await scanResourceFolder(cid)
  const cached = Object.values(scanned.episodes).reduce((sum, set) => sum + set.size, 0)
  const seasons = Object.keys(scanned.episodes).map(Number).sort((a, b) => a - b)
  let tmdbTotal = Number(row.total_episodes || 0)
  let latestEpisode = Number(row.latest_episode || 0)
  let poster = row.poster_url || ''
  let overview = row.overview || ''
  const seasonTotals: Record<number, number> = {}
  if (row.tmdb_id) {
    try {
      const detail = await tmdbRequest(`/${row.media_type || 'tv'}/${row.tmdb_id}`)
      const mapped = mapTmdbDetail(detail, row.media_type || 'tv')
      if (mapped) {
        tmdbTotal = mapped.total_episodes || tmdbTotal
        poster = mapped.poster_url || poster
        overview = mapped.overview || overview
        latestEpisode = await fetchAiredCount(row.tmdb_id, row.media_type || 'tv')
        for (const s of mapped.seasons) seasonTotals[s.season_number] = s.episode_count
      }
    } catch { /* TMDB 不可用时保留旧数据 */ }
  }
  const seasonsJson = JSON.stringify(seasons.map(s => ({
    season: s,
    cached: scanned.episodes[s].size,
    total: seasonTotals[s] || 0,
  })))
  const updated: Resource = {
    ...row,
    folder_id_115: cid,
    total_episodes: tmdbTotal,
    cached_episodes: cached,
    latest_episode: latestEpisode,
    seasons_json: seasonsJson,
    replace_rules_json: '[]',
    poster_url: poster,
    overview,
    file_count: scanned.files.length,
    total_size: scanned.files.reduce((sum, f) => sum + Number(f.size || 0), 0),
    last_synced_at: nowIso(),
    updated_at: nowIso(),
  }
  await cache.writeFiles(id, scanned.files)
  await writeResources(items.map(r => r.id === id ? updated : r))
  return {
    ok: true,
    item: updated,
    stats: {
      ok: true,
      files: scanned.files.length,
      episodes_cached: cached,
      total_episodes: tmdbTotal,
      seasons,
      seasons_json: seasonsJson,
      truncated: scanned.truncated,
    },
  }
}

async function resourceMatches(files: ResourceFile[]): Promise<ImportMatch[]> {
  const items = await readResources()
  const lookup = new Map<string, { resource: Resource; file: ResourceFile }>()
  for (const resource of items) {
    const resourceFiles = (await cache.readFiles(resource.id)) || []
    for (const file of resourceFiles) {
      lookup.set(`${file.display_name || file.name || file.filename}\u0000${Number(file.size || file.file_size || 0)}`, { resource, file })
    }
  }
  const result = new Map<number, ImportMatch>()
  for (const file of files) {
    const hit = lookup.get(`${file.display_name || file.name}\u0000${Number(file.size || 0)}`)
    if (!hit) continue
    const entry = result.get(hit.resource.id) || {
      resource_id: hit.resource.id,
      title: hit.resource.title,
      path_115: hit.resource.path_115,
      matched_file_ids: [] as string[],
    }
    entry.matched_file_ids.push(file.fid)
    result.set(hit.resource.id, entry)
  }
  return [...result.values()]
}

function parseShareUrl(url: string): { shareCode: string; password: string } {
  const m = /\/s\/([a-zA-Z0-9]+)/.exec(url)
  const password = new URLSearchParams(new URL(url).search).get('password') || ''
  return { shareCode: m?.[1] || '', password }
}

export const directApi = {
  async getSession(): Promise<PanSession> {
    return { ok: await checkCookie(), cached: false }
  },
  async login(): Promise<PanSession> {
    return { ok: false, error: '账号密码登录已移除，请使用扫码授权' }
  },
  async logout(): Promise<{ ok: boolean }> {
    await clearSessionCookies()
    return { ok: true }
  },
  async createQrLogin(): Promise<QrLogin> {
    for (const base of QR_BASES) {
      try {
        const res = await nativeRequest(`${base}/api/1.0/web/1.0/token/`)
        const token = res.data
        const uid = String(token?.uid || '')
        if (!uid) continue
        qrTokens.set(uid, { time: String(token.time || ''), sign: String(token.sign || ''), base })
        return { ok: true, uid, qr_url: `${base}/api/1.0/web/1.0/qrcode?uid=${uid}`, expires_in: 300 }
      } catch { /* try next host */ }
    }
    return { ok: false, error: '二维码服务不可用' }
  },
  async getQrLoginStatus(uid: string): Promise<QrLoginStatus> {
    const entry = qrTokens.get(uid)
    if (!entry) return { ok: false, status: 'expired', error: '二维码已过期，请重新生成' }
    try {
      const state = await nativeRequest(`${entry.base}/get/status/`, {
        params: { uid, time: entry.time, sign: entry.sign },
      })
      const body = state.data
      const status = Number(body?.status ?? body?.data?.status ?? 0)
      if (status !== 2) {
        const labels: Record<string, QrLoginStatus['status']> = { 0: 'waiting', 1: 'scanned', '-1': 'expired', '-2': 'canceled' }
        return { ok: true, status: labels[status] || 'waiting' }
      }
      const result = await nativeRequest(`${entry.base}/app/1.0/alipaymini/1.0/login/qrcode/`, {
        method: 'POST',
        form: { account: uid },
      })
      const resultBody = result.data
      const cookie = serializeCookie(resultBody?.cookie || resultBody?.data?.cookie)
      if (!cookie) return { ok: true, status: 'confirmed', error: '扫码已确认，正在获取授权凭据' }
      const fullCookie = /\bUID=/i.test(cookie) ? cookie : `${cookie}; uid=${uid}`
      await setSessionCookies(fullCookie)
      qrTokens.delete(uid)
      return { ok: true, status: 'authorized' }
    } catch (error: any) {
      return { ok: false, status: 'waiting', error: String(error?.message || error) }
    }
  },
  async cancelQrLogin(): Promise<{ ok: boolean }> {
    return { ok: true }
  },
  async browsePanDir(cid: string): Promise<PanDir> {
    const items = await listDir(cid || '0')
    return { ok: true, cid: cid || '0', items }
  },
  async getReceiveHistory(): Promise<{ ok: boolean; total?: number; records?: ReceiveRecord[] }> {
    try {
      const res = await nativeRequest('https://webapi.115.com/history/receive_list', {
        params: { limit: 1150, offset: 0 },
      })
      const body = res.data
      if (!body?.state) return { ok: false }
      const d = body.data || {}
      const list: any[] = d.list || []
      return {
        ok: true,
        total: Number(d.total || list.length),
        records: list.map(r => ({
          id: String(r.id || ''),
          name: String(r.file_name || ''),
          parent_name: String(r.parent_name || ''),
          file_size: Number(r.file_size || 0),
          create_time: Number(r.create_time || 0),
          update_time: Number(r.update_time || 0),
        })),
      }
    } catch {
      return { ok: false }
    }
  },
  async clearReceiveHistory(ids: string[]): Promise<{ ok: boolean; deleted?: number }> {
    try {
      const res = await nativeRequest('https://webapi.115.com/history/delete', {
        method: 'POST',
        form: { id: ids.join(','), with_file: '0' },
      })
      const ok = Boolean(res.data?.state)
      return { ok, deleted: ok ? ids.length : undefined }
    } catch {
      return { ok: false }
    }
  },
  async getResources(query = ''): Promise<{ ok: boolean; items: Resource[] }> {
    const items = await readResources()
    const q = query.toLowerCase()
    return {
      ok: true,
      items: q ? items.filter(r => `${r.title} ${r.path_115}`.toLowerCase().includes(q)) : items,
    }
  },
  async syncAllResources(): Promise<{ ok: boolean; task_id?: string; result?: { synced?: number; errors?: string[] }; error?: string }> {
    const items = await readResources()
    const errors: string[] = []
    let synced = 0
    for (const item of items) {
      const result = await syncResourceItem(item.id)
      if (result.ok) synced += 1
      else errors.push(`${item.title}：${result.error || '同步失败'}`)
    }
    return { ok: true, result: { synced, errors: errors.slice(0, 30) } }
  },
  async getResource(id: number): Promise<ResourceDetail> {
    const items = await readResources()
    const item = items.find(r => r.id === id)
    if (!item) throw new Error('资源不存在')
    return { ok: true, item, files: (await cache.readFiles(id)) || [] }
  },
  async deleteResource(id: number): Promise<{ ok: boolean }> {
    const items = await readResources()
    await writeResources(items.filter(r => r.id !== id))
    await cache.removeFiles(id)
    return { ok: true }
  },
  async previewImport(url: string, password: string): Promise<ImportPreview> {
    const { shareCode, password: pwFromUrl } = parseShareUrl(url)
    if (!shareCode) throw new Error('无法解析 115 分享链接')
    const info = await getShareInfo(shareCode, password || pwFromUrl)
    if (!info.state) throw new Error(info.error || '分享链接不可用')
    const files = (info.files || []).map(f => ({ ...f, display_name: f.name }))
    return {
      ok: true,
      share_code: shareCode,
      title: info.title || '未命名资源',
      files,
      matches: await resourceMatches(files),
    }
  },
  async importFiles(payload: {
    url: string; password: string; title: string; target_path?: string; resource_id?: number;
    file_ids: string[]; files: ResourceFile[]
  }): Promise<{ ok: boolean; resource_id?: number; target_path?: string; error?: string }> {
    const { shareCode, password: pwFromUrl } = parseShareUrl(payload.url)
    if (!shareCode) return { ok: false, error: '无法解析 115 分享链接' }
    const items = await readResources()
    const existing = payload.resource_id ? items.find(r => r.id === payload.resource_id) : null
    const path115 = payload.target_path || existing?.path_115 || ''
    if (!path115) return { ok: false, error: '请选择或新建保存目录' }
    const cid = await ensurePath(path115)
    if (!cid) return { ok: false, error: '无法创建或访问目标目录' }
    const existingFiles = new Set<string>()
    for (const item of await listDir(cid)) existingFiles.add(`${item.name}\u0000${item.size}`)
    const duplicates: string[] = []
    const toSave = payload.file_ids.filter(fid => {
      const file = payload.files.find(f => f.fid === fid)
      if (!file) return false
      const effective = file.name || ''
      if (existingFiles.has(`${effective}\u0000${file.size}`)) {
        duplicates.push(effective)
        return false
      }
      return true
    })
    if (duplicates.length) return { ok: false, error: `以下文件已存在于 115 目标目录，已阻止重复保存：${duplicates.slice(0, 10).join('、')}` }
    if (!toSave.length) return { ok: false, error: '没有需要保存的文件' }
    const saved = await saveFilesToPan(shareCode, payload.password || pwFromUrl, cid, toSave.join(','))
    if (!saved.ok) {
      const errText = saved.error || '转存失败'
      if (errText.includes('已接收') || errText.includes('无需重复接收')) {
        throw Object.assign(new Error('115 提示这些文件已接收过，需要先清理接收记录'), {
          data: { code: 'ALREADY_RECEIVED', error: errText, receive_records: [] },
        })
      }
      return { ok: false, error: errText }
    }
    const { files: rawFiles } = await listTreeFiles(cid)
    const files = rawFiles.map(f => ({ ...f, display_name: f.name }))
    const id = existing?.id || (await cache.nextId())
    const title = payload.title || path115.split('/').filter(Boolean).pop() || path115
    const item = buildResource({ ...(existing || {}), title, path_115: path115, folder_id_115: cid, replace_rules_json: '[]' }, files, id)
    const nextItems = existing ? items.map(r => r.id === id ? item : r) : [...items, item]
    await cache.writeFiles(id, files)
    await writeResources(nextItems)
    await syncResourceItem(id)
    return { ok: true, resource_id: id, target_path: path115 }
  },
  async addResourceFolder(payload: {
    path_115: string; title?: string; tmdb_id?: number | null; media_type?: string;
    poster_url?: string; overview?: string; total_episodes?: number
  }): Promise<{ ok: boolean; task_id?: string; item: Resource; items?: Resource[]; sync?: ResourceSyncResult; index_truncated?: boolean; error?: string }> {
    const cid = await findCidByPath(payload.path_115)
    if (!cid) throw new Error('在 115 网盘中找不到该目录，请先确认路径')
    const title = payload.title?.trim() || payload.path_115.split('/').filter(Boolean).pop() || payload.path_115
    const id = await cache.nextId()
    const { files: rawFiles, truncated } = await listTreeFiles(cid)
    const files = rawFiles.map(f => ({ ...f, display_name: f.name }))
    const item = buildResource({
      title,
      path_115: payload.path_115,
      folder_id_115: cid,
      tmdb_id: payload.tmdb_id ?? null,
      media_type: payload.media_type || 'tv',
      poster_url: payload.poster_url || '',
      overview: payload.overview || '',
      total_episodes: payload.total_episodes || 0,
      replace_rules_json: '[]',
    }, files, id)
    await cache.writeFiles(id, files)
    const items = await readResources()
    await writeResources([...items, item])
    const sync = await syncResourceItem(id)
    const finalItem = sync.item || item
    return { ok: true, item: finalItem, items: [finalItem], sync: sync.stats, index_truncated: truncated }
  },
  async syncResource(id: number): Promise<{ ok: boolean; item: Resource; stats: ResourceSyncResult }> {
    const result = await syncResourceItem(id)
    if (!result.ok || !result.item || !result.stats) throw new Error(result.error || '同步失败')
    return { ok: true, item: result.item, stats: result.stats }
  },
  async updateResourceTitle(id: number, title: string): Promise<{ ok: boolean; item: Resource }> {
    const items = await readResources()
    const row = items.find(r => r.id === id)
    if (!row) throw new Error('资源不存在')
    const updated = { ...row, title: title.trim(), match_key: matchKey(title.trim()), updated_at: nowIso() }
    await writeResources(items.map(r => r.id === id ? updated : r))
    return { ok: true, item: updated }
  },
  async refreshTmdb(id: number): Promise<{ ok: boolean; item: Resource }> {
    const items = await readResources()
    const row = items.find(r => r.id === id)
    if (!row) throw new Error('资源不存在')
    if (!row.tmdb_id) throw new Error('该资源尚未关联 TMDB')
    const result = await tmdbRequest(`/${row.media_type || 'tv'}/${row.tmdb_id}`)
    const mapped = mapTmdbDetail(result, row.media_type || 'tv')
    if (!mapped) throw new Error('TMDB 请求失败，请检查 API Key')
    const updated = {
      ...row,
      poster_url: mapped.poster_url || row.poster_url,
      overview: mapped.overview || row.overview,
      total_episodes: mapped.total_episodes || row.total_episodes,
      latest_episode: await fetchAiredCount(row.tmdb_id, row.media_type || 'tv'),
      media_type: row.media_type || 'tv',
      updated_at: nowIso(),
    }
    await writeResources(items.map(r => r.id === id ? updated : r))
    return { ok: true, item: updated }
  },
  async renamePreview(id: number, prefix: string): Promise<{ ok: boolean; prefix?: string; suggested_prefix?: string | null; total?: number; parsed?: number; items?: { fid: string; name: string; new_name: string | null; current_prefix?: string | null; same_prefix?: boolean; no_episode?: boolean; will_rename: boolean }[] }> {
    const items = await readResources()
    const row = items.find(r => r.id === id)
    if (!row) throw new Error('资源不存在')
    const files = (await cache.readFiles(id)) || []
    const counts = new Map<string, number>()
    for (const f of files) {
      const p = episodePrefix(f.name || '')
      if (p) counts.set(p, (counts.get(p) || 0) + 1)
    }
    const suggested = [...counts.entries()].sort((a, b) => b[1] - a[1])[0]?.[0] || null
    const cleanPrefix = (prefix || suggested || row.title || '').trim()
    const preview = files.map(f => {
      const newName = buildPatternName(cleanPrefix, f.name || '')
      const currentPrefix = episodePrefix(f.name || '')
      const samePrefix = Boolean(currentPrefix && prefixesMatch(currentPrefix, cleanPrefix))
      const noEpisode = !parseEpisode(f.name || '')
      const ext = (f.name || '').split('.').pop() || ''
      const effectiveNew = newName || (noEpisode && ext ? `${cleanPrefix}.${ext}` : null)
      return {
        fid: f.fid,
        name: f.name || '',
        new_name: effectiveNew,
        current_prefix: currentPrefix,
        same_prefix: samePrefix,
        no_episode: noEpisode,
        will_rename: Boolean(effectiveNew && effectiveNew !== f.name && !samePrefix && !noEpisode),
      }
    })
    preview.sort((a, b) => {
      const ap = parseEpisode(a.name)
      const bp = parseEpisode(b.name)
      const aSeason = ap?.season ?? Number.MAX_SAFE_INTEGER
      const bSeason = bp?.season ?? Number.MAX_SAFE_INTEGER
      const aEp = ap?.episode ?? Number.MAX_SAFE_INTEGER
      const bEp = bp?.episode ?? Number.MAX_SAFE_INTEGER
      if (aSeason !== bSeason) return aSeason - bSeason
      if (aEp !== bEp) return aEp - bEp
      return a.name.localeCompare(b.name)
    })
    return { ok: true, prefix: cleanPrefix, suggested_prefix: suggested, total: preview.length, parsed: preview.filter(i => i.new_name).length, items: preview }
  },
  async renameResourceFile(id: number, fid: string, newName: string): Promise<{ ok: boolean; file?: ResourceFile }> {
    const items = await readResources()
    const row = items.find(r => r.id === id)
    if (!row) throw new Error('资源不存在')
    const files = (await cache.readFiles(id)) || []
    const file = files.find(f => f.fid === fid)
    if (!file) throw new Error('文件不在当前资源索引中')
    const oldName = file.name || ''
    if (oldName === newName) return { ok: true, file }
    const oldExt = oldName.split('.').pop()?.toLowerCase()
    const newExt = newName.split('.').pop()?.toLowerCase()
    if (oldExt !== newExt) throw new Error('新文件名扩展名必须与原来一致')
    await nativeRequest('https://webapi.115.com/files/edit', {
      method: 'POST',
      form: { fid, file_name: newName },
    })
    const parsed = parseEpisode(newName)
    const updated: ResourceFile = {
      ...file,
      name: newName,
      filename: newName,
      display_name: newName,
      season_number: parsed?.season ?? null,
      episode_number: parsed?.episode ?? null,
    }
    await cache.writeFiles(id, files.map(f => f.fid === fid ? updated : f))
    return { ok: true, file: updated }
  },
  async renameResourceFiles(id: number, prefix: string, options?: { renames?: { fid: string; old_name: string; new_name: string }[]; concurrency?: number; interval_ms?: number }): Promise<{
    ok: boolean
    task_id?: string
    result?: { renamed?: number; skipped?: number; skipped_samples?: string[]; errors?: string[]; item?: Resource }
    error?: string
  }> {
    const items = await readResources()
    const row = items.find(r => r.id === id)
    if (!row) throw new Error('资源不存在')
    let cid = row.folder_id_115 || ''
    if (!cid) cid = (await findCidByPath(row.path_115)) || ''
    if (!cid) throw new Error(`在 115 网盘中找不到目录: ${row.path_115}`)
    const concurrency = Math.max(1, Math.min(Number(options?.concurrency || 1), 5))
    const interval = Math.max(0, Number(options?.interval_ms || 300)) / 1000
    const tasks: { fid: string; old: string; newName: string }[] = []
    let renamed = 0
    let skipped = 0
    const skippedSamples: string[] = []
    const errors: string[] = []
    if (options?.renames?.length) {
      for (const r of options.renames) {
        if (!r.fid || !r.old_name || !r.new_name || r.new_name === r.old_name) continue
        if (r.new_name.split('.').pop()?.toLowerCase() !== r.old_name.split('.').pop()?.toLowerCase()) {
          skipped += 1
          if (skippedSamples.length < 10) skippedSamples.push(`${r.old_name}：扩展名不一致，已跳过`)
          continue
        }
        tasks.push({ fid: r.fid, old: r.old_name, newName: r.new_name })
      }
    } else {
      const scanned = await scanResourceFolder(cid)
      const cleanPrefix = (prefix || row.title || '').trim()
      for (const file of scanned.files) {
        const currentPrefix = episodePrefix(file.name || '')
        const newName = buildPatternName(cleanPrefix, file.name || '')
        if (currentPrefix && prefixesMatch(currentPrefix, cleanPrefix)) continue
        if (!newName) {
          skipped += 1
          if (skippedSamples.length < 10) skippedSamples.push(file.name || '')
          continue
        }
        if (newName === file.name) continue
        tasks.push({ fid: file.fid, old: file.name || '', newName })
      }
    }
    let index = 0
    const runners = Array.from({ length: concurrency }, async () => {
      while (index < tasks.length) {
        const task = tasks[index++]
        if (!task) break
      try {
        await nativeRequest('https://webapi.115.com/files/edit', {
          method: 'POST',
          form: { fid: task.fid, file_name: task.newName },
        })
        renamed += 1
      } catch (error: any) {
        errors.push(`${task.old} → ${task.newName}：${error?.message || error}`)
      }
        if (interval > 0) await new Promise(resolve => setTimeout(resolve, interval * (0.7 + Math.random() * 0.6) * 1000))
      }
    })
    await Promise.all(runners)
    const updated = { ...row, replace_rules_json: '[]', updated_at: nowIso() }
    await writeResources(items.map(r => r.id === id ? updated : r))
    await syncResourceItem(id)
    const finalItem = (await readResources()).find(r => r.id === id)
    return { ok: true, result: { renamed, skipped, skipped_samples: skippedSamples, errors: errors.slice(0, 30), item: finalItem } }
  },
  async attachTmdb(id: number, payload: {
    tmdb_id: number; media_type?: string; title?: string; poster_url?: string; overview?: string; total_episodes?: number
  }): Promise<{ ok: boolean; item: Resource; stats: ResourceSyncResult }> {
    const items = await readResources()
    const row = items.find(r => r.id === id)
    if (!row) throw new Error('资源不存在')
    const updated = {
      ...row,
      tmdb_id: payload.tmdb_id,
      media_type: payload.media_type || 'tv',
      title: payload.title?.trim() || row.title,
      poster_url: payload.poster_url || row.poster_url,
      overview: payload.overview || row.overview,
      updated_at: nowIso(),
    }
    await writeResources(items.map(r => r.id === id ? updated : r))
    const result = await syncResourceItem(id)
    if (!result.ok || !result.item || !result.stats) throw new Error(result.error || '同步失败')
    return { ok: true, item: result.item, stats: result.stats }
  },
  async getTmdbConfig(): Promise<{ configured: boolean; enabled: boolean }> {
    const configured = Boolean(localStorage.getItem(TMDB_KEY))
    return { configured, enabled: configured }
  },
  posterProxyUrl(url: string): string {
    return url
  },
  async setTmdbConfig(apiKey: string): Promise<{ ok: boolean }> {
    localStorage.setItem(TMDB_KEY, apiKey.trim())
    return { ok: true }
  },
  async searchTmdb(query: string, mediaType = 'tv'): Promise<TmdbSearchResult> {
    const result = await tmdbRequest(`/search/${mediaType === 'movie' ? 'movie' : 'tv'}`, { query })
    if (!result) return { ok: false, items: [], total_results: 0, error: 'TMDB API Key 未配置，请在设置页配置' }
    return {
      ok: true,
      items: mapTmdbItems(result.results || [], mediaType),
      total_results: Number(result.total_results || 0),
    }
  },
  async getTmdbDetail(id: number, mediaType = 'tv'): Promise<TmdbDetail> {
    const result = await tmdbRequest(`/${mediaType === 'movie' ? 'movie' : 'tv'}/${id}`)
    const mapped = mapTmdbDetail(result, mediaType)
    if (!mapped) return { ok: false, tmdb_id: id, media_type: mediaType, title: '', original_title: '', year: '', overview: '', poster_url: '', backdrop_url: '', total_episodes: 0, number_of_seasons: 0, seasons: [], status: '', error: 'TMDB API Key 未配置或请求失败' }
    return mapped
  },
  async addCloudDownload(magnetUrl: string, targetPath?: string): Promise<{ ok: boolean; task_id?: string; error?: string }> {
    return addCloudDownload(magnetUrl, targetPath || '')
  },
  async getDownloadTasks(page = 1): Promise<{ state?: boolean; tasks?: DownloadTask[] }> {
    return getDownloadTasks(page)
  },
  async getTaskStatus(): Promise<{ ok: boolean; done: boolean; stage: string; current: number; total: number; error?: string | null; result?: null }> {
    return { ok: false, done: true, stage: '直连模式无需后台任务', current: 0, total: 0, error: null, result: null }
  },
}
