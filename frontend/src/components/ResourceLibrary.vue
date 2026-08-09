<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api } from '../api'
import { useResourceCache } from '../composables/useResourceCache'
import { useToast } from '../composables/useToast'
import { useTaskProgress } from '../composables/useTaskProgress'
import type { PanDirItem, RenamePreviewItem, Resource, ResourceFile, TmdbSearchItem } from '../types'
import VirtualList from './VirtualList.vue'

const emit = defineEmits<{ import: [] }>()
const { show: toast } = useToast()
const taskProgress = useTaskProgress()
const cache = useResourceCache()

const query = ref('')
const resources = ref<Resource[]>([])
const loading = ref(true)
const deleting = ref<number | null>(null)
const syncing = ref<number | null>(null)
const tmdbSyncing = ref<number | null>(null)

const selected = ref<Resource | null>(null)
const files = ref<ResourceFile[]>([])
const detailLoading = ref(false)

const addOpen = ref(false)
const browseCid = ref('0')
const browsePath = ref('')
const browseItems = ref<PanDirItem[]>([])
const browseLoading = ref(false)
const browseStack = ref<{ name: string; cid: string }[]>([])
const newTitle = ref('')
const newPath = ref('')

const attachOpen = ref(false)
const attachQuery = ref('')
const attachResults = ref<TmdbSearchItem[]>([])
const attachSearching = ref(false)
const attachChosen = ref<TmdbSearchItem | null>(null)
const attaching = ref(false)

const addTmdbQuery = ref('')
const addTmdbResults = ref<TmdbSearchItem[]>([])
const addTmdbSearching = ref(false)
const addTmdbChosen = ref<TmdbSearchItem | null>(null)
const adding = ref(false)
const editingTitle = ref(false)
const titleDraft = ref('')
const renameOpen = ref(false)
const renamePrefix = ref('')
const renamePreview = ref<RenamePreviewItem[]>([])
const renameSelected = ref(new Set<string>())
const renameOverrides = ref(new Map<string, string>())
const renameConcurrency = ref(1)
const renameInterval = ref(300)
const renameShowOnlyNeeded = ref(true)
const renamePreviewLoading = ref(false)
const renameSubmitting = ref(false)
const renameBusyFid = ref('')
const renameTmdbOpen = ref(false)
const renameTmdbQuery = ref('')
const renameTmdbResults = ref<TmdbSearchItem[]>([])
const renameTmdbSearching = ref(false)
const renameTmdbChosen = ref<TmdbSearchItem | null>(null)
const posters = ref<Record<number, string>>({})
const posterUrls = new Map<number, string>()

const shown = computed(() => resources.value.filter(r =>
  !query.value || `${r.title} ${r.path_115}`.toLowerCase().includes(query.value.toLowerCase()),
))
const renameVisibleItems = computed(() =>
  renameShowOnlyNeeded.value ? renamePreview.value.filter(i => i.will_rename) : renamePreview.value,
)
const renameNeedCount = computed(() => renamePreview.value.filter(i => i.will_rename).length)
const renamePlainCount = computed(() => renamePreview.value.filter(i => i.no_episode && i.new_name && i.new_name !== i.name).length)
const renameSameCount = computed(() => renamePreview.value.filter(i => i.same_prefix && !i.will_rename).length)
const renameUnknownCount = computed(() => renamePreview.value.filter(i => !i.new_name).length)

function formatSize(bytes: number) {
  if (!bytes) return '0 B'
  const gb = bytes / 1024 ** 3
  return gb >= 1 ? `${gb.toFixed(1)} GB` : `${(bytes / 1024 ** 2).toFixed(1)} MB`
}
function formatDate(value: string) {
  return value ? new Date(value).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) : '-'
}
function seasons(item: Resource) {
  try { return JSON.parse(item.seasons_json || '[]') as { season: number; cached: number; total: number }[] } catch { return [] }
}
function progress(item: Resource) {
  const denominator = item.latest_episode || item.total_episodes
  if (!denominator) return 0
  return Math.min(100, Math.round((item.cached_episodes / denominator) * 100))
}
function episodeLabel(item: Resource) {
  if (!item.tmdb_id) return item.cached_episodes ? `已识别 ${item.cached_episodes} 集` : '未关联 TMDB'
  if (item.latest_episode > 0) return `已存 ${item.cached_episodes} / 已播出 ${item.latest_episode} 集`
  return `已存 ${item.cached_episodes} / ${item.total_episodes || '?'} 集`
}
async function load() {
  loading.value = true
  try {
    const result = await api.getResources()
    resources.value = result.items
    cache.write(result.items)
    for (const item of result.items) cachePoster(item)
    if (selected.value) await reloadDetailFiles(selected.value.id)
  } catch {
    const saved = await cache.read()
    if (saved) {
      resources.value = saved
      toast('正在显示本地缓存，连接恢复后会自动更新', 'info')
    } else {
      toast('资源库暂时无法加载', 'error')
    }
  } finally { loading.value = false }
}

async function syncAll() {
  taskProgress.start('正在从 115 同步资源库')
  try {
    const result = await api.syncAllResources()
    if (result.task_id) {
      pollSyncAll(result.task_id)
    } else {
      await load()
      taskProgress.finish()
      const errors = result.result?.errors || []
      toast(errors.length ? `已同步 ${result.result?.synced || 0} 个资源，${errors.length} 个失败` : `已同步 ${result.result?.synced || 0} 个资源`, errors.length ? 'error' : 'success')
    }
  } catch (error: any) {
    taskProgress.finish()
    toast(error.data?.error || error.message || '同步失败', 'error')
  }
}
function pollSyncAll(taskId: string) {
  let attempts = 0
  const timer = window.setInterval(async () => {
    attempts += 1
    try {
      const task = await api.getTaskStatus(taskId)
      taskProgress.update(task.stage, task.current || 0, task.total || 0)
      if (task.done) {
        window.clearInterval(timer)
        if (task.error) {
          taskProgress.fail(task.error)
          toast(task.error, 'error')
        } else {
          await load()
          taskProgress.update('全部完成，正在刷新', task.current || 0, task.total || 0)
          const errors = task.result?.errors || []
          toast(errors.length ? `已同步 ${task.result?.synced || 0} 个资源，${errors.length} 个失败` : `已同步 ${task.result?.synced || 0} 个资源`, errors.length ? 'error' : 'success')
          window.setTimeout(() => taskProgress.finish(), 1200)
        }
      }
    } catch {
      if (attempts > 300) {
        window.clearInterval(timer)
        taskProgress.fail('全量同步超时，请稍后重试')
      }
    }
  }, 900)
}

async function cachePoster(item: Resource) {
  if (!item.poster_url || posters.value[item.id]) return
  try {
    const cached = await cache.readPoster(item.id)
    if (cached) {
      const url = URL.createObjectURL(cached)
      posterUrls.set(item.id, url)
      posters.value[item.id] = url
      return
    }
    const response = await fetch(api.posterProxyUrl(item.poster_url))
    if (!response.ok) return
    const blob = await response.blob()
    await cache.writePoster(item.id, blob)
    const url = URL.createObjectURL(blob)
    posterUrls.set(item.id, url)
    posters.value[item.id] = url
  } catch { /* 海报缓存失败不影响主流程 */ }
}

function applyItem(item: Resource) {
  const index = resources.value.findIndex(r => r.id === item.id)
  if (index >= 0) resources.value[index] = item
  if (selected.value?.id === item.id) selected.value = item
  cache.write(resources.value)
  cachePoster(item)
}

async function reloadDetailFiles(resourceId: number) {
  if (selected.value?.id !== resourceId) return
  try {
    const result = await api.getResource(resourceId)
    files.value = [...result.files].sort((a, b) => {
      const aSeason = a.season_number ?? Number.MAX_SAFE_INTEGER
      const bSeason = b.season_number ?? Number.MAX_SAFE_INTEGER
      if (aSeason !== bSeason) return aSeason - bSeason
      const aEp = a.episode_number ?? Number.MAX_SAFE_INTEGER
      const bEp = b.episode_number ?? Number.MAX_SAFE_INTEGER
      if (aEp !== bEp) return aEp - bEp
      return String(a.display_name || a.filename || a.name).localeCompare(String(b.display_name || b.filename || b.name))
    })
  } catch { /* 保留旧列表 */ }
}

function startEditTitle() {
  if (!selected.value) return
  titleDraft.value = selected.value.title
  editingTitle.value = true
}
async function saveTitle() {
  if (!selected.value || !titleDraft.value.trim()) return
  try {
    const result = await api.updateResourceTitle(selected.value.id, titleDraft.value.trim())
    const index = resources.value.findIndex(r => r.id === selected.value!.id)
    if (index >= 0) resources.value[index] = result.item
    selected.value = result.item
    cache.write(resources.value)
    editingTitle.value = false
    toast('名称已更新（仅本地显示）', 'success')
  } catch (error: any) {
    toast(error.data?.error || error.message || '修改失败', 'error')
  }
}

async function openDetail(item: Resource) {
  selected.value = item
  files.value = []
  detailLoading.value = true
  try {
    const result = await api.getResource(item.id)
    files.value = [...result.files].sort((a, b) => {
      const aSeason = a.season_number ?? Number.MAX_SAFE_INTEGER
      const bSeason = b.season_number ?? Number.MAX_SAFE_INTEGER
      if (aSeason !== bSeason) return aSeason - bSeason
      const aEp = a.episode_number ?? Number.MAX_SAFE_INTEGER
      const bEp = b.episode_number ?? Number.MAX_SAFE_INTEGER
      if (aEp !== bEp) return aEp - bEp
      return String(a.display_name || a.filename || a.name).localeCompare(String(b.display_name || b.filename || b.name))
    })
  } catch {
    toast('无法读取资源文件', 'error')
  } finally { detailLoading.value = false }
}
function closeDetail() { selected.value = null; attachOpen.value = false }

async function remove(item: Resource) {
  if (!confirm(`移除“${item.title}”的本地索引？115 云端文件不会被删除。`)) return
  deleting.value = item.id
  try {
    await api.deleteResource(item.id)
    const posterUrl = posterUrls.get(item.id)
    if (posterUrl) URL.revokeObjectURL(posterUrl)
    posterUrls.delete(item.id)
    delete posters.value[item.id]
    await cache.removePoster(item.id)
    resources.value = resources.value.filter(r => r.id !== item.id)
    cache.write(resources.value)
    if (selected.value?.id === item.id) selected.value = null
    toast('已移除本地索引', 'success')
  } catch {
    toast('移除失败', 'error')
  } finally { deleting.value = null }
}

async function sync(item: Resource) {
  syncing.value = item.id
  try {
    const result = await api.syncResource(item.id)
    applyItem(result.item)
    await reloadDetailFiles(item.id)
    toast(result.stats.truncated ? '同步完成（目录较大，部分文件未索引）' : '集数已同步', 'success')
  } catch (error: any) {
    toast(error.data?.error || error.message || '同步失败', 'error')
  } finally { syncing.value = null }
}

async function refreshTmdb(item: Resource) {
  if (!item.tmdb_id) { toast('请先关联 TMDB', 'error'); return }
  tmdbSyncing.value = item.id
  try {
    const result = await api.refreshTmdb(item.id)
    applyItem(result.item)
    await reloadDetailFiles(item.id)
    toast('TMDB 数据已同步', 'success')
  } catch (error: any) {
    toast(error.data?.error || error.message || 'TMDB 同步失败', 'error')
  } finally { tmdbSyncing.value = null }
}

function openRename() {
  if (!selected.value) return
  renamePrefix.value = ''
  renamePreview.value = []
  renameSelected.value = new Set()
  renameOverrides.value = new Map()
  renameShowOnlyNeeded.value = true
  renameTmdbOpen.value = false
  renameTmdbQuery.value = ''
  renameTmdbResults.value = []
  renameTmdbChosen.value = null
  renameOpen.value = true
  loadRenamePreview()
}
async function loadRenamePreview() {
  if (!selected.value || !renamePrefix.value.trim()) { renamePreview.value = []; return }
  renamePreviewLoading.value = true
  try {
    const result = await api.renamePreview(selected.value.id, renamePrefix.value.trim())
    renamePreview.value = result.items || []
    if (!renamePrefix.value.trim() && result.suggested_prefix) {
      renamePrefix.value = result.suggested_prefix
    } else if (!renamePrefix.value.trim() && result.prefix) {
      renamePrefix.value = result.prefix
    }
    renameOverrides.value = new Map()
    renameSelected.value = new Set(renamePreview.value.filter(i => i.will_rename).map(i => i.fid))
  } catch (error: any) {
    renamePreview.value = []
    toast(error.data?.error || error.message || '预览失败', 'error')
  } finally { renamePreviewLoading.value = false }
}
async function runRenameTmdbSearch() {
  if (!renameTmdbQuery.value.trim()) return
  renameTmdbSearching.value = true
  try {
    const result = await api.searchTmdb(renameTmdbQuery.value.trim(), 'tv')
    renameTmdbResults.value = result.items || []
    renameTmdbChosen.value = null
  } catch (error: any) {
    renameTmdbResults.value = []
    toast(error.data?.error || error.message || 'TMDB 搜索失败', 'error')
  } finally { renameTmdbSearching.value = false }
}
function pickRenameTmdb(item: TmdbSearchItem) {
  renameTmdbChosen.value = item
  renamePrefix.value = item.title
  renameTmdbOpen.value = false
  loadRenamePreview()
}
function effectiveRenameName(item: RenamePreviewItem) {
  return renameOverrides.value.get(item.fid) || item.new_name || ''
}
function onRenameInput(fid: string, event: Event) {
  const next = new Map(renameOverrides.value)
  next.set(fid, (event.target as HTMLInputElement).value)
  renameOverrides.value = next
}
function toggleRenameItem(fid: string) {
  const next = new Set(renameSelected.value)
  next.has(fid) ? next.delete(fid) : next.add(fid)
  renameSelected.value = next
}
function setAllRename(select: boolean) {
  renameSelected.value = new Set(select
    ? renamePreview.value.filter(i => i.new_name && i.new_name !== i.name).map(i => i.fid)
    : [])
}
async function renameOne(item: RenamePreviewItem) {
  if (!selected.value || renameBusyFid.value) return
  const newName = effectiveRenameName(item).trim()
  if (!newName || newName === item.name) return
  renameBusyFid.value = item.fid
  try {
    const result = await api.renameResourceFile(selected.value.id, item.fid, newName)
    if (!result.ok) throw new Error('重命名失败')
    toast(`已重命名：${item.name} → ${newName}`, 'success')
    await reloadDetailFiles(selected.value.id)
    await loadRenamePreview()
  } catch (error: any) {
    toast(error.data?.error || error.message || '重命名失败', 'error')
  } finally { renameBusyFid.value = '' }
}
async function submitRename() {
  if (!selected.value) return
  const renames = renamePreview.value
    .filter(i => renameSelected.value.has(i.fid))
    .map(i => ({ fid: i.fid, old_name: i.name, new_name: effectiveRenameName(i).trim() }))
    .filter(r => r.new_name && r.new_name !== r.old_name)
  if (!renames.length) { toast('请至少选择 1 个需要改名的文件', 'error'); return }
  renameSubmitting.value = true
  taskProgress.start(`正在批量重命名 ${renames.length} 个文件`)
  try {
    const result = await api.renameResourceFiles(selected.value.id, renamePrefix.value.trim(), {
      renames,
      concurrency: renameConcurrency.value,
      interval_ms: renameInterval.value,
    })
    if (result.task_id) {
      pollRenameTask(result.task_id)
    } else {
      taskProgress.finish()
      if (result.result?.item) applyItem(result.result.item)
      if (selected.value) await reloadDetailFiles(selected.value.id)
      toast(`已重命名 ${result.result?.renamed || 0} 个文件`, 'success')
    }
  } catch (error: any) {
    taskProgress.finish()
    toast(error.data?.error || error.message || '批量重命名失败', 'error')
  } finally { renameSubmitting.value = false }
}
function pollRenameTask(taskId: string) {
  let attempts = 0
  const timer = window.setInterval(async () => {
    attempts += 1
    try {
      const task = await api.getTaskStatus(taskId)
      taskProgress.update(task.stage, task.current || 0, task.total || 0)
      if (task.done) {
        window.clearInterval(timer)
        if (task.error) {
          taskProgress.fail(task.error)
          toast(task.error, 'error')
        } else {
          if (task.result?.item) applyItem(task.result.item)
          if (selected.value) await reloadDetailFiles(selected.value.id)
          const renamed = task.result?.renamed ?? 0
          const skipped = task.result?.skipped ?? 0
          const errors = task.result?.errors || []
          const total = task.total || (renamed + skipped + errors.length)
          taskProgress.update('全部完成，正在刷新', task.current || 0, task.total || 0)
          const skipText = skipped ? `，${skipped} 个无法识别集数已跳过` : ''
          toast(errors.length ? `已重命名 ${renamed}/${total} 个${skipText}，${errors.length} 个失败` : `已重命名 ${renamed}/${total} 个文件${skipText}`, errors.length ? 'error' : 'success')
          if (renameOpen.value) await loadRenamePreview()
          window.setTimeout(() => taskProgress.finish(), 1200)
        }
      }
    } catch {
      if (attempts > 240) {
        window.clearInterval(timer)
        taskProgress.fail('批量重命名超时，请稍后重试')
      }
    }
  }, 900)
}

async function browseDir(cid: string) {
  browseLoading.value = true
  try {
    const result = await api.browsePanDir(cid)
    browseItems.value = result.items
    browseCid.value = result.cid
  } catch (error: any) {
    toast(error.data?.error || error.message || '无法读取 115 目录', 'error')
  } finally { browseLoading.value = false }
}
function enterDir(dir: PanDirItem) {
  if (!dir.is_dir) return
  browseStack.value.push({ name: dir.name, cid: dir.fid })
  browsePath.value = browseStack.value.map(s => s.name).join('/')
  newTitle.value = dir.name
  addTmdbQuery.value = dir.name
  newPath.value = browsePath.value
  browseDir(dir.fid)
}
function upDir() {
  browseStack.value.pop()
  browsePath.value = browseStack.value.map(s => s.name).join('/')
  newPath.value = browsePath.value
  const cid = browseStack.value.length ? browseStack.value[browseStack.value.length - 1].cid : '0'
  browseDir(cid)
}
function useCurrentDir() {
  if (!browsePath.value) return
  newPath.value = browsePath.value
  newTitle.value = newTitle.value || browsePath.value.split('/').pop() || ''
}
function openAdd() {
  addOpen.value = true
  browseCid.value = '0'
  browsePath.value = ''
  browseStack.value = []
  newTitle.value = ''
  newPath.value = ''
  addTmdbChosen.value = null
  addTmdbResults.value = []
  addTmdbQuery.value = ''
  browseDir('0')
}
async function addFolder() {
  if (!newPath.value) { toast('请先选择 115 目录', 'error'); return }
  adding.value = true
  try {
    addOpen.value = false
    taskProgress.start('正在添加目录')
    const result = await api.addResourceFolder({
      path_115: newPath.value,
      title: newTitle.value || undefined,
      tmdb_id: addTmdbChosen.value?.tmdb_id ?? null,
      media_type: addTmdbChosen.value?.media_type || 'tv',
      poster_url: addTmdbChosen.value?.poster_url || '',
      overview: addTmdbChosen.value?.overview || '',
      total_episodes: 0,
    })
    if (result.task_id) {
      pollTask(result.task_id)
    } else {
      taskProgress.finish()
      const added = result.items?.length ? result.items : (result.item ? [result.item] : [])
      for (const item of added) {
        if (!resources.value.some(r => r.id === item.id)) resources.value.unshift(item)
      }
      if (added.length) {
        cache.write(resources.value)
      }
      toast(added.length > 1 ? `已加入 ${added.length} 个资源` : '已加入资源库', 'success')
    }
  } catch (error: any) {
    taskProgress.finish()
    toast(error.data?.error || error.message || '添加失败', 'error')
  } finally { adding.value = false }
}

function pollTask(taskId: string) {
  let attempts = 0
  const timer = window.setInterval(async () => {
    attempts += 1
    try {
      const task = await api.getTaskStatus(taskId)
      taskProgress.update(task.stage, task.current || 0, task.total || 0)
      if (task.done) {
        window.clearInterval(timer)
        if (task.error) {
          taskProgress.fail(task.error)
          toast(task.error, 'error')
        } else {
          const added = task.result?.items?.length ? task.result.items : (task.result?.item ? [task.result.item] : [])
          for (const item of added) {
            if (!resources.value.some(r => r.id === item.id)) resources.value.unshift(item)
          }
          if (added.length) {
            cache.write(resources.value)
          }
          await load()
          taskProgress.update('全部完成，正在刷新', task.current || 0, task.total || 0)
          toast(added.length > 1 ? `已加入 ${added.length} 个资源` : '已加入资源库', 'success')
          window.setTimeout(() => taskProgress.finish(), 1200)
        }
      }
    } catch {
      if (attempts > 180) {
        window.clearInterval(timer)
        taskProgress.fail('添加目录超时，请稍后在资源库刷新')
      }
    }
  }, 900)
}

async function runTmdbSearch(target: 'add' | 'attach') {
  const q = target === 'add' ? addTmdbQuery.value : attachQuery.value
  if (!q.trim()) return
  if (target === 'add') { addTmdbSearching.value = true } else { attachSearching.value = true }
  try {
    const result = await api.searchTmdb(q.trim())
    if (!result.ok) throw new Error(result.error || 'TMDB 搜索失败')
    if (target === 'add') addTmdbResults.value = result.items
    else attachResults.value = result.items
  } catch (error: any) {
    toast(error.message || 'TMDB 搜索失败', 'error')
    if (target === 'add') addTmdbResults.value = []
    else attachResults.value = []
  } finally {
    if (target === 'add') addTmdbSearching.value = false
    else attachSearching.value = false
  }
}
function pickAddTmdb(item: TmdbSearchItem) {
  addTmdbChosen.value = item
  if (!newTitle.value) newTitle.value = item.title
}
function openAttach() {
  attachOpen.value = true
  attachQuery.value = ''
  attachResults.value = []
  attachChosen.value = null
}
function pickAttach(item: TmdbSearchItem) { attachChosen.value = item }
async function attachTmdb() {
  if (!selected.value || !attachChosen.value) return
  attaching.value = true
  try {
    const result = await api.attachTmdb(selected.value.id, {
      tmdb_id: attachChosen.value.tmdb_id,
      media_type: attachChosen.value.media_type,
      title: attachChosen.value.title,
      poster_url: attachChosen.value.poster_url,
      overview: attachChosen.value.overview,
    })
    const index = resources.value.findIndex(r => r.id === selected.value!.id)
    if (index >= 0) resources.value[index] = result.item
    selected.value = result.item
    cache.write(resources.value)
    cachePoster(result.item)
    attachOpen.value = false
    toast('已关联 TMDB', 'success')
  } catch (error: any) {
    toast(error.data?.error || error.message || '关联失败', 'error')
  } finally { attaching.value = false }
}

onMounted(load)
</script>

<template>
  <section class="library-page">
    <header class="page-head">
      <div>
        <p class="eyebrow">115 RESOURCE LIBRARY</p>
        <h1>资源库</h1>
        <p>读取 115 网盘已有目录，随时对比已保存集数与 TMDB 总集数。</p>
      </div>
      <div class="head-actions">
        <button class="btn btn-ghost" :disabled="loading" @click="syncAll">
          <span v-if="loading" class="spinner" /><span v-else>↻</span>从115同步
        </button>
        <button class="btn btn-ghost" @click="openAdd">添加目录</button>
        <button class="btn btn-primary" @click="emit('import')">导入链接</button>
      </div>
    </header>

    <div class="toolbar">
      <input v-model="query" type="search" placeholder="搜索资源名称或 115 目录" />
      <span>{{ resources.length }} 个资源</span>
    </div>

    <div v-if="loading" class="loading"><span class="spinner" /> 正在读取资源库</div>
    <div v-else-if="shown.length === 0" class="empty">
      <b>资源库为空</b>
      <p>可以从 115 网盘选择一个已有目录加入，或导入分享链接。</p>
      <button class="btn btn-primary" @click="openAdd">添加 115 目录</button>
    </div>
    <div v-else class="resource-grid">
      <article v-for="item in shown" :key="item.id" class="resource" @click="openDetail(item)">
        <div class="poster">
          <img v-if="item.poster_url" :src="posters[item.id] || item.poster_url" alt="" loading="lazy" />
          <span v-else>🎬</span>
        </div>
        <div class="resource-main">
          <h2>{{ item.title }}</h2>
          <p class="path">{{ item.path_115 }}</p>
          <div class="episode-row">
            <span class="ep-badge" :class="{ linked: item.tmdb_id }">{{ episodeLabel(item) }}</span>
            <span class="progress" v-if="item.tmdb_id"><i :style="{ width: progress(item) + '%' }" /></span>
          </div>
          <div class="meta">
            <span>{{ item.file_count }} 个文件</span>
            <span>{{ formatSize(item.total_size) }}</span>
            <span>{{ formatDate(item.updated_at) }}</span>
          </div>
        </div>
        <button class="icon-btn danger" title="移除本地索引" :disabled="deleting === item.id" @click.stop="remove(item)">×</button>
      </article>
    </div>

    <aside v-if="selected" class="detail" @click.self="closeDetail">
      <div class="detail-panel">
        <header>
          <div class="detail-top">
            <img v-if="selected.poster_url" class="detail-poster" :src="selected.poster_url" alt="" />
            <div class="detail-heading">
              <p class="eyebrow">RESOURCE DETAIL</p>
              <h2 v-if="!editingTitle">{{ selected.title }}</h2>
              <div v-else class="title-edit">
                <input v-model="titleDraft" type="text" @keyup.enter="saveTitle" />
                <button class="btn btn-ghost btn-sm" @click="saveTitle">保存</button>
                <button class="btn btn-ghost btn-sm" @click="editingTitle = false">取消</button>
              </div>
              <p>{{ selected.path_115 }}</p>
              <p v-if="selected.overview" class="overview">{{ selected.overview }}</p>
              <div class="episode-row big">
                <span class="ep-badge" :class="{ linked: selected.tmdb_id }">已存 {{ selected.cached_episodes }} / 已播出 {{ selected.latest_episode || selected.total_episodes || '?' }} 集<template v-if="selected.latest_episode && selected.total_episodes && selected.total_episodes !== selected.latest_episode">（总 {{ selected.total_episodes }}）</template></span>
                <span class="progress" v-if="selected.tmdb_id"><i :style="{ width: progress(selected) + '%' }" /></span>
              </div>
            </div>
          </div>
          <div class="detail-actions">
            <button class="btn btn-ghost btn-sm" :disabled="syncing === selected.id" @click="sync(selected)">
              <span v-if="syncing === selected.id" class="spinner" />{{ syncing === selected.id ? '同步中' : '同步集数' }}
            </button>
            <button class="btn btn-ghost btn-sm" @click="openAttach">关联 TMDB</button>
            <button class="btn btn-ghost btn-sm" :disabled="tmdbSyncing === selected.id" @click="refreshTmdb(selected)">
              <span v-if="tmdbSyncing === selected.id" class="spinner" />{{ tmdbSyncing === selected.id ? '同步中' : '同步 TMDB' }}
            </button>
            <button class="btn btn-ghost btn-sm" @click="openRename">批量重命名</button>
            <button class="btn btn-ghost btn-sm" @click="startEditTitle">改名称</button>
            <button class="btn btn-ghost btn-sm danger-text" :disabled="deleting === selected.id" @click="remove(selected)">移除索引</button>
            <button class="icon-btn" title="关闭" @click="closeDetail">×</button>
          </div>
        </header>

        <div v-if="seasons(selected).length" class="seasons">
          <span v-for="s in seasons(selected)" :key="s.season" class="season-chip">
            S{{ s.season }} · 已存 {{ s.cached }}<template v-if="s.total"> / {{ s.total }}</template>
          </span>
        </div>

        <div class="file-head"><span>文件</span><span>{{ files.length }} 项</span></div>
        <div class="file-list">
          <div v-if="detailLoading" class="loading"><span class="spinner" /> 读取中</div>
          <VirtualList v-else :items="files" :item-height="40" :height="420" key-field="fid">
            <template #default="{ item }">
              <div class="file-row">
                <span>{{ item.display_name || item.filename || item.name }}<em v-if="item.season_number && item.episode_number">S{{ item.season_number }}E{{ item.episode_number }}</em></span>
                <small>{{ formatSize(Number(item.file_size || item.size || 0)) }}</small>
              </div>
            </template>
          </VirtualList>
        </div>
      </div>
    </aside>

    <div v-if="addOpen" class="modal-mask" @click.self="addOpen = false">
      <div class="modal">
        <header><div><p class="eyebrow">ADD FROM PAN</p><h2>添加 115 目录</h2></div><button class="icon-btn" @click="addOpen = false">×</button></header>
        <div class="breadcrumbs">
          <button class="link-btn" @click="upDir">← 上级</button>
          <code>/{{ browsePath }}</code>
        </div>
        <div class="dir-list">
          <div v-if="browseLoading" class="loading"><span class="spinner" /> 读取目录中</div>
          <button v-for="dir in browseItems.filter(i => i.is_dir)" :key="dir.fid" class="dir-row" @click="enterDir(dir)">
            📁 {{ dir.name }}
          </button>
          <p v-if="!browseLoading && !browseItems.filter(i => i.is_dir).length" class="muted">当前目录没有子文件夹，可直接使用此目录。</p>
        </div>
        <button class="btn btn-ghost btn-block" :disabled="!browsePath" @click="useCurrentDir">使用当前目录：/{{ browsePath || '（未选择）' }}</button>

        <div class="add-form">
          <label>资源名称<input v-model="newTitle" type="text" placeholder="默认使用目录名" /></label>
          <div class="tmdb-line">
            <input v-model="addTmdbQuery" type="search" placeholder="搜索 TMDB 剧集并关联（可选）" @keyup.enter="runTmdbSearch('add')" />
            <button class="btn btn-ghost btn-sm" :disabled="addTmdbSearching" @click="runTmdbSearch('add')">搜索</button>
          </div>
          <div v-if="addTmdbResults.length" class="tmdb-results">
            <button v-for="item in addTmdbResults" :key="item.tmdb_id" class="tmdb-row" :class="{ chosen: addTmdbChosen?.tmdb_id === item.tmdb_id }" @click="pickAddTmdb(item)">
              <img v-if="item.poster_url" :src="item.poster_url" alt="" loading="lazy" />
              <span><b>{{ item.title }}</b><small>{{ item.year }} · {{ item.overview }}</small></span>
              <em v-if="addTmdbChosen?.tmdb_id === item.tmdb_id">✓</em>
            </button>
          </div>
          <button class="btn btn-primary btn-block" :disabled="adding || !newPath" @click="addFolder">
            <span v-if="adding" class="spinner" /><span v-else>加入资源库并同步</span>
          </button>
        </div>
      </div>
    </div>

    <div v-if="attachOpen && selected" class="modal-mask" @click.self="attachOpen = false">
      <div class="modal">
        <header><div><p class="eyebrow">LINK TMDB</p><h2>关联 TMDB</h2></div><button class="icon-btn" @click="attachOpen = false">×</button></header>
        <div class="tmdb-line">
          <input v-model="attachQuery" type="search" placeholder="输入剧名搜索" @keyup.enter="runTmdbSearch('attach')" />
          <button class="btn btn-ghost btn-sm" :disabled="attachSearching" @click="runTmdbSearch('attach')">搜索</button>
        </div>
        <div v-if="attachResults.length" class="tmdb-results">
          <button v-for="item in attachResults" :key="item.tmdb_id" class="tmdb-row" :class="{ chosen: attachChosen?.tmdb_id === item.tmdb_id }" @click="pickAttach(item)">
            <img v-if="item.poster_url" :src="item.poster_url" alt="" loading="lazy" />
            <span><b>{{ item.title }}</b><small>{{ item.year }} · {{ item.overview }}</small></span>
            <em v-if="attachChosen?.tmdb_id === item.tmdb_id">✓</em>
          </button>
        </div>
        <p v-else-if="!attachSearching && !attachResults.length" class="muted">在设置页配置 TMDB API Key 后可搜索剧集。</p>
        <button class="btn btn-primary btn-block" :disabled="attaching || !attachChosen" @click="attachTmdb">
          <span v-if="attaching" class="spinner" /><span v-else>关联并同步集数</span>
        </button>
      </div>
    </div>

    <div v-if="renameOpen" class="modal-mask" @click.self="renameOpen = false">
      <div class="modal">
        <header><div><p class="eyebrow">BATCH RENAME</p><h2>批量重命名</h2></div><button class="icon-btn" @click="renameOpen = false">×</button></header>
        <p class="rename-hint">修改的是 115 网盘里的真实文件名。点任意一行即可勾选；目标前缀默认取 S01E01 之前的名称，可手动改或用 TMDB 名称。前缀已一致的不会改动。115 没有官方批量改名接口，勾选后逐个执行，可调并发/间隔防风控。</p>
        <div class="rename-pattern-row">
          <label>目标前缀<input v-model="renamePrefix" type="text" placeholder="例如 斗罗大陆2：绝世唐门" @keyup.enter="loadRenamePreview" /></label>
          <button class="btn btn-ghost btn-sm" :disabled="renamePreviewLoading || renameSubmitting" @click="loadRenamePreview"><span v-if="renamePreviewLoading" class="spinner" /><span v-else>识别 / 刷新</span></button>
          <button class="btn btn-ghost btn-sm" :disabled="renameSubmitting" @click="renameTmdbOpen = !renameTmdbOpen">{{ renameTmdbOpen ? '收起 TMDB' : '用 TMDB 名称' }}</button>
        </div>
        <div v-if="renameTmdbOpen" class="rename-tmdb">
          <div class="tmdb-line">
            <input v-model="renameTmdbQuery" type="search" placeholder="输入剧名搜索" @keyup.enter="runRenameTmdbSearch" />
            <button class="btn btn-ghost btn-sm" :disabled="renameTmdbSearching" @click="runRenameTmdbSearch">搜索</button>
          </div>
          <div v-if="renameTmdbResults.length" class="tmdb-results">
            <button v-for="item in renameTmdbResults" :key="item.tmdb_id" class="tmdb-row" :class="{ chosen: renameTmdbChosen?.tmdb_id === item.tmdb_id }" @click="pickRenameTmdb(item)">
              <img v-if="item.poster_url" :src="item.poster_url" alt="" loading="lazy" />
              <span><b>{{ item.title }}</b><small>{{ item.year }} · {{ item.overview }}</small></span>
              <em v-if="renameTmdbChosen?.tmdb_id === item.tmdb_id">✓</em>
            </button>
          </div>
          <p v-else-if="!renameTmdbSearching && !renameTmdbResults.length" class="muted">搜索后点一个结果，目标前缀会替换为 TMDB 名称。</p>
        </div>
        <div class="rename-options">
          <label class="only-needed"><input type="checkbox" v-model="renameShowOnlyNeeded" :disabled="renameSubmitting" /> 只看需修改</label>
          <label>并发 <select v-model.number="renameConcurrency" :disabled="renameSubmitting"><option :value="1">1（最稳）</option><option :value="2">2</option><option :value="3">3</option><option :value="5">5（快）</option></select></label>
          <label>间隔 <select v-model.number="renameInterval" :disabled="renameSubmitting"><option :value="300">0.3s</option><option :value="500">0.5s</option><option :value="1000">1s</option></select></label>
          <button class="link-btn" :disabled="renameSubmitting" @click="setAllRename(true)">全选</button>
          <button class="link-btn" :disabled="renameSubmitting" @click="setAllRename(false)">取消全选</button>
        </div>
        <div v-if="renamePreview.length" class="rename-preview">
          <div class="rename-preview-head">
            <span>需修改 {{ renameNeedCount }}</span>
            <span>已选 {{ renameSelected.size }} 个</span>
            <span>无集数 {{ renamePlainCount }}</span>
            <span>无需修改 {{ renameSameCount }}</span>
            <span>无法识别 {{ renameUnknownCount }}</span>
          </div>
          <div class="rename-preview-list">
            <VirtualList :items="renameVisibleItems" :item-height="58" :height="320" key-field="fid">
              <template #default="{ item }">
                <div class="rename-preview-row" :class="{ selected: renameSelected.has(item.fid), skip: !(item.new_name && item.new_name !== item.name), clickable: Boolean(item.new_name && item.new_name !== item.name), plain: item.no_episode }" :title="item.no_episode ? '无集数：将改成纯名称，需手动勾选' : item.name" @click="(item.new_name && item.new_name !== item.name) && toggleRenameItem(item.fid)">
                  <input v-if="item.new_name && item.new_name !== item.name" type="checkbox" :disabled="renameSubmitting" :checked="renameSelected.has(item.fid)" @click.stop="toggleRenameItem(item.fid)" />
                  <span v-else class="skip-dot">×</span>
                  <span class="old" :title="item.name">{{ item.name }}</span>
                  <em>→</em>
                  <input v-if="item.new_name" class="new-input" :placeholder="item.no_episode ? '纯名称（无集数）' : '新文件名'" :value="effectiveRenameName(item)" :disabled="renameBusyFid === item.fid || renameSubmitting" @click.stop @input="onRenameInput(item.fid, $event)" />
                  <span v-else class="new">{{ item.same_prefix ? '前缀已一致，无需修改' : '无法识别集数，跳过' }}</span>
                  <button v-if="item.new_name && item.new_name !== item.name" class="link-btn rename-one" :disabled="(renameBusyFid !== '' && renameBusyFid !== item.fid) || renameSubmitting" @click.stop="renameOne(item)">{{ renameBusyFid === item.fid ? '…' : '改这个' }}</button>
                  <span v-else class="rename-one" />
                </div>
              </template>
            </VirtualList>
          </div>
        </div>
        <p v-else class="rename-hint muted">暂无预览结果，点击“识别 / 刷新”或输入目标前缀。</p>
        <button class="btn btn-primary btn-block" :disabled="renameSubmitting || !renameSelected.size" @click="submitRename">
          <span v-if="renameSubmitting" class="spinner" /><span v-else>重命名已选 {{ renameSelected.size }} 个文件</span>
        </button>
      </div>
    </div>
  </section>
</template>

<style scoped>
.library-page { max-width: 1100px; margin: 0 auto; }
.page-head { display: flex; justify-content: space-between; align-items: end; gap: 16px; margin-bottom: 22px; }
.eyebrow { font-size: 11px; color: var(--accent); margin: 0 0 7px; font-weight: 700; }
.page-head h1 { font-size: 28px; margin: 0 0 8px; }
.page-head p:not(.eyebrow) { color: var(--text-secondary); font-size: 14px; margin: 0; }
.head-actions { display: flex; gap: 10px; }
.toolbar { display: flex; gap: 14px; align-items: center; margin-bottom: 16px; }
.toolbar input { max-width: 420px; flex: 1; }
.toolbar span { font-size: 12px; color: var(--text-muted); white-space: nowrap; }
.loading { display: flex; align-items: center; gap: 10px; color: var(--text-secondary); font-size: 13px; padding: 30px 0; justify-content: center; }
.empty { text-align: center; padding: 64px 20px; color: var(--text-secondary); }
.empty b { display: block; font-size: 18px; color: var(--text-primary); margin-bottom: 8px; }
.empty p { font-size: 13px; margin: 0 0 18px; }
.resource-grid { display: grid; grid-template-columns: 1fr; gap: 10px; }
.resource { position: relative; display: flex; gap: 12px; padding: 12px; background: var(--bg-card); border: 1px solid var(--border); border-radius: 9px; cursor: pointer; }
.poster { width: 72px; height: 104px; flex: 0 0 auto; border-radius: 5px; overflow: hidden; background: var(--bg-card-hover); display: grid; place-items: center; font-size: 26px; }
.poster img { width: 100%; height: 100%; object-fit: cover; display: block; }
.resource-main { min-width: 0; flex: 1; }
.resource h2 { font-size: 15px; margin: 0 0 4px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.path { margin: 0 0 8px; color: var(--text-muted); font-size: 11px; font-family: ui-monospace, monospace; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.episode-row { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.ep-badge { font-size: 11px; color: var(--text-secondary); background: var(--bg-card-hover); padding: 3px 8px; border-radius: 99px; white-space: nowrap; }
.ep-badge.linked { color: var(--success); }
.progress { flex: 1; max-width: 120px; height: 4px; border-radius: 99px; background: var(--bg-card-hover); overflow: hidden; }
.progress i { display: block; height: 100%; background: var(--accent); border-radius: 99px; }
.meta { display: flex; gap: 10px; flex-wrap: wrap; color: var(--text-muted); font-size: 11px; }
.icon-btn { border: 0; background: transparent; color: var(--text-secondary); font-size: 18px; cursor: pointer; line-height: 1; padding: 6px; }
.icon-btn.danger, .danger-text { color: var(--danger); }
.detail { position: fixed; inset: 0; z-index: 50; background: rgb(0 0 0 / 0.55); display: flex; justify-content: flex-end; }
.detail-panel { width: min(640px, 100%); height: 100%; background: var(--bg-primary); border-left: 1px solid var(--border); overflow-y: auto; padding: 22px; }
.detail-panel header { border-bottom: 1px solid var(--border); padding-bottom: 16px; }
.detail-top { display: flex; gap: 16px; }
.detail-poster { width: 110px; height: 160px; border-radius: 7px; object-fit: cover; flex: 0 0 auto; background: var(--bg-card-hover); }
.detail-heading { min-width: 0; }
.detail-heading h2 { font-size: 22px; margin: 0 0 6px; } .title-edit { display: flex; gap: 8px; align-items: center; margin-bottom: 6px; } .title-edit input { min-width: 0; flex: 1; padding: 8px 10px; font-size: 15px; }
.detail-heading > p { color: var(--text-secondary); font-size: 12px; margin: 0 0 6px; font-family: ui-monospace, monospace; }
.detail-heading .overview { font-family: inherit; color: var(--text-muted); font-size: 12px; line-height: 1.5; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
.episode-row.big { margin: 10px 0 0; }
.episode-row.big .progress { max-width: none; height: 6px; }
.detail-actions { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; margin-top: 14px; }
.detail-actions .icon-btn { margin-left: auto; }
.seasons { display: flex; gap: 8px; flex-wrap: wrap; padding: 14px 0; border-bottom: 1px solid var(--border); }
.season-chip { font-size: 12px; color: var(--text-secondary); background: var(--bg-card); border: 1px solid var(--border); padding: 5px 10px; border-radius: 99px; }
.file-head { display: flex; justify-content: space-between; padding: 14px 0 6px; font-size: 12px; color: var(--text-secondary); }
.file-row { min-height: 40px; display: flex; align-items: center; gap: 10px; border-bottom: 1px solid var(--border); font-size: 13px; } .file-list .virtual-row .file-row { height: 100%; min-height: 0; }
.file-row span { min-width: 0; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.file-row em { font-style: normal; color: var(--accent); margin-left: 8px; font-size: 11px; }
.file-row small { color: var(--text-muted); font-size: 11px; }
.modal-mask { position: fixed; inset: 0; z-index: 60; background: rgb(0 0 0 / 0.6); display: grid; place-items: center; padding: 14px; }
.modal { width: min(560px, 100%); max-height: 86vh; overflow-y: auto; background: var(--bg-primary); border: 1px solid var(--border); border-radius: 10px; padding: 20px; }
.modal header { display: flex; justify-content: space-between; align-items: start; margin-bottom: 14px; }
.modal h2 { font-size: 19px; margin: 0; } .rename-hint { font-size: 12px; color: var(--text-secondary); line-height: 1.5; margin: 0 0 12px; } .rename-pattern-row { display: grid; grid-template-columns: 1fr auto auto; gap: 10px; align-items: end; margin-bottom: 10px; } .rename-pattern-row label { display: grid; gap: 6px; font-size: 12px; color: var(--text-secondary); } .rename-pattern-row input { min-width: 0; } .rename-tmdb { display: grid; gap: 8px; margin-bottom: 10px; padding: 10px; border: 1px solid var(--border); border-radius: 7px; background: var(--bg-card); } .rename-options { display: flex; align-items: center; gap: 14px; margin-bottom: 10px; font-size: 12px; color: var(--text-secondary); flex-wrap: wrap; } .rename-options label { display: flex; align-items: center; gap: 6px; } .rename-options .only-needed { white-space: nowrap; } .rename-options select { background: var(--bg-card); color: var(--text-primary); border: 1px solid var(--border); border-radius: 6px; padding: 5px 8px; font-size: 12px; } .rename-preview { display: grid; gap: 8px; margin-bottom: 12px; } .rename-preview-head { display: flex; gap: 14px; font-size: 12px; color: var(--text-muted); flex-wrap: wrap; } .rename-preview-list { border: 1px solid var(--border); border-radius: 7px; overflow: hidden; } .rename-preview-row { display: grid; grid-template-columns: auto minmax(0,1fr) auto minmax(0,1fr) auto; gap: 8px; align-items: center; padding: 0 12px; font-size: 12px; border-bottom: 1px solid var(--border); } .rename-preview-row:last-child { border-bottom: 0; } .rename-preview-row.clickable { cursor: pointer; } .rename-preview-row.clickable:hover { background: var(--bg-card-hover); } .rename-preview-row.selected { background: color-mix(in srgb, var(--accent) 12%, transparent); } .rename-preview-row.selected .old { color: var(--text-primary); } .rename-preview-row .old { color: var(--text-secondary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; } .rename-preview-row .new { color: var(--text-muted); } .rename-preview-row .new-input { min-width: 0; font-size: 12px; } .rename-preview-row em { font-style: normal; color: var(--text-muted); } .rename-preview-row .rename-one { white-space: nowrap; min-height: 18px; } .rename-preview-row .skip-dot { color: var(--text-muted); font-weight: 700; text-align: center; width: 14px; } .rename-preview-row.skip .old { color: var(--text-muted); } .rename-preview-row.plain .old { color: var(--accent); } .rename-preview-row.plain .new-input { border-color: color-mix(in srgb, var(--accent) 45%, transparent); }
.breadcrumbs { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; font-size: 12px; }
.breadcrumbs code { color: var(--text-secondary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.dir-list { max-height: 230px; overflow-y: auto; border: 1px solid var(--border); border-radius: 7px; margin-bottom: 12px; }
.dir-row { display: block; width: 100%; text-align: left; background: transparent; border: 0; border-bottom: 1px solid var(--border); padding: 11px 14px; color: var(--text-primary); font-size: 13px; cursor: pointer; }
.dir-row:last-child { border-bottom: 0; }
.add-form, .add-form label { display: grid; gap: 10px; }
.add-form { margin-top: 16px; }
.add-form label { font-size: 12px; color: var(--text-secondary); }
.tmdb-line { display: flex; gap: 8px; }
.tmdb-line input { flex: 1; }
.tmdb-results { display: grid; gap: 6px; max-height: 240px; overflow-y: auto; }
.tmdb-row { display: flex; gap: 10px; align-items: center; text-align: left; color: var(--text-primary); background: var(--bg-card); border: 1px solid var(--border); border-radius: 7px; padding: 8px; cursor: pointer; }
.tmdb-row.chosen { border-color: var(--accent); }
.tmdb-row img { width: 38px; height: 56px; object-fit: cover; border-radius: 4px; flex: 0 0 auto; }
.tmdb-row span { min-width: 0; flex: 1; display: grid; gap: 2px; }
.tmdb-row b { font-size: 13px; }
.tmdb-row small { color: var(--text-muted); font-size: 11px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tmdb-row em { color: var(--success); font-style: normal; }
.muted { color: var(--text-muted); font-size: 12px; }
.btn-block { width: 100%; }
@media (min-width: 640px) {
  .resource-grid { grid-template-columns: repeat(2, 1fr); }
  .detail-panel { padding: 28px; }
}
@media (min-width: 980px) {
  .resource-grid { grid-template-columns: repeat(3, 1fr); }
}
@media (max-width: 520px) {
  .page-head { display: grid; }
  .head-actions { display: grid; grid-template-columns: 1fr 1fr; }
  .toolbar { display: grid; }
  .toolbar input { max-width: none; }
  .detail { justify-content: center; }
  .detail-panel { width: 100%; padding: 16px; }
  .detail-top { display: grid; grid-template-columns: 88px 1fr; gap: 12px; }
  .detail-poster { width: 88px; height: 128px; }
  .detail-actions .btn { flex: 1; }
}
</style>
