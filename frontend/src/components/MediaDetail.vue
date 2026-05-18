<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { api } from '../api'
import { useToast } from '../composables/useToast'
import EpisodeThumb from './EpisodeThumb.vue'
import type { WatchlistItem } from '../types'

const props = defineProps<{
  item: WatchlistItem
}>()

const emit = defineEmits<{
  close: []
  navigateShare: [path: string]
}>()

const { show: toast } = useToast()

// Detail
const detail = ref<WatchlistItem>(props.item)

// Path editing
const editingPath = ref(false)
const newPath = ref(props.item.path_115)
const savingPath = ref(false)

// Sync
const syncing = ref(false)

// Episodes (from cache API)
const allEpisodes = ref<any[]>([])
const seasonPosters = ref<Record<number, string>>({})
const loadingEps = ref(false)

// Season
const activeSeason = ref(1)
const seasons = computed(() => {
  const nums = new Set<number>()
  for (const ep of allEpisodes.value) nums.add(ep.season_number)
  if (nums.size === 0) nums.add(1)
  return Array.from(nums).sort((a, b) => a - b)
})

// Current season episodes (filtered: only aired)
const today = new Date().toISOString().slice(0, 10)
const currentEpisodes = computed(() => {
  return allEpisodes.value
    .filter(ep => ep.season_number === activeSeason.value)
    .filter(ep => !ep.air_date || ep.air_date <= today)
    .sort((a, b) => a.episode_number - b.episode_number)
})

// Stats
const totalCached = computed(() =>
  allEpisodes.value.filter(ep => ep.cached_file).length
)
const displayLatest = computed(() =>
  detail.value?.latest_episode || detail.value?.total_episodes || 0
)

async function loadDetail() {
  const res = await api.getWatchlistDetail(props.item.id)
  if (res.ok && res.item) detail.value = res.item
}

async function loadEpisodes(season?: number) {
  loadingEps.value = true
  try {
    const res = await api.getMediaEpisodes(props.item.id)
    if (res.ok && res.episodes) {
      allEpisodes.value = res.episodes
      seasonPosters.value = res.season_posters || {}
      // Auto-select first season
      if (res.episodes.length > 0 && !season) {
        const snSet = new Set<number>()
        for (const e of res.episodes) snSet.add(e.season_number)
        const sns = Array.from(snSet).sort((a, b) => a - b)
        if (sns.length > 0) activeSeason.value = sns[0]
      }
    }
  } catch { /* empty */ }
  finally { loadingEps.value = false }
}

onMounted(() => {
  loadDetail()
  loadEpisodes()
})

watch(activeSeason, () => {/* lazy load handled by eps API */})

function onPosterError(e: Event) {
  const img = e.currentTarget as HTMLImageElement
  if (!img) return
  img.style.display = 'none'
  const next = img.nextElementSibling as HTMLElement
  if (next) next.classList.add('show')
}

// Background: season poster → backdrop
const bgImage = computed(() => {
  if (seasonPosters.value[activeSeason.value]) return seasonPosters.value[activeSeason.value]
  return detail.value?.backdrop_path || ''
})

const displayOverview = computed(() => detail.value?.overview || '')

// TMDB ID editing
const editingTmdb = ref(false)
const newTmdbId = ref<number | null>(null)
const savingTmdb = ref(false)

function startEditTmdb() {
  newTmdbId.value = detail.value?.tmdb_id || null
  editingTmdb.value = true
}

async function handleSaveTmdb() {
  savingTmdb.value = true
  try {
    const tid = newTmdbId.value || null
    await api.updateWatchlist(props.item.id, { tmdb_id: tid as any })
    detail.value = { ...detail.value, tmdb_id: tid as any }
    editingTmdb.value = false
    toast('TMDB ID 已更新，请重新同步以获取数据', 'success')
  } catch { toast('更新失败', 'error') }
  finally { savingTmdb.value = false }
}

// Path
async function handleSavePath() {
  savingPath.value = true
  try {
    await api.updateWatchlist(props.item.id, { path_115: newPath.value.trim() })
    detail.value = { ...detail.value, path_115: newPath.value.trim() }
    editingPath.value = false
    toast('路径已更新', 'success')
  } catch { toast('更新失败', 'error') }
  finally { savingPath.value = false }
}

// Sync
async function handleSync() {
  syncing.value = true
  try {
    const res = await api.syncWatchlist(props.item.id) as any
    if (res.ok) {
      const eps = res.episodes_cached || 0
      const files = res.files_cached || 0
      const sc = res.season_count || 0
      const debug = res.debug || ''
      if (files === 0) toast('目录为空或路径不正确' + (debug ? ` (${debug})` : ''), 'info')
      else toast(`同步完成：${files} 文件, ${eps} 集, ${sc} 季`, 'success')
    } else {
      toast(res.error || '同步失败', 'error')
    }
    await loadDetail()
    await loadEpisodes()
  } catch { toast('同步请求失败', 'error') }
  finally { syncing.value = false }
}

function handleGoShare() {
  emit('navigateShare', detail.value?.path_115 || '')
}

async function handleDelete() {
  if (!confirm('确定删除？')) return
  try { await api.deleteWatchlist(props.item.id); toast('已删除', 'success'); emit('close') }
  catch { toast('删除失败', 'error') }
}

function getStatusLabel(s: string) {
  return { tracking: '追更中', completed: '已完结', paused: '已暂停' }[s] || s
}
function getRegionLabel(r: string) {
  return { cn: '中国', jp: '日本', west: '欧美' }[r] || r.toUpperCase()
}
</script>

<template>
  <Teleport to="body">
    <div class="modal-overlay" @click.self="emit('close')">
      <div class="modal-card">
        <button class="close-btn" @click="emit('close')">✕</button>

        <!-- Background image -->
        <div class="modal-bg">
          <img v-if="bgImage" :src="bgImage" alt="" />
          <div class="bg-gradient"></div>
          <!-- Episode overlay when selected -->
        </div>

        <div class="modal-body">
          <!-- Left column -->
          <div class="modal-left">
            <img v-if="detail.poster_path" :src="detail.poster_path" class="poster" @error="onPosterError" />
            <div v-else class="poster placeholder"><span>🎬</span></div>
            <h2>{{ detail.title }}</h2>
            <div v-if="detail.original_title" class="orig">{{ detail.original_title }}</div>
            <div class="tags">
              <span class="tag">{{ getRegionLabel(detail.region) }}</span>
              <span :class="['tag', detail.status]">{{ getStatusLabel(detail.status) }}</span>
            </div>

            <!-- Stats -->
            <div class="stats">
              <span>📦 已缓存 <b>{{ totalCached }}</b> 集</span>
              <span v-if="displayLatest > 0">📡 已更至 <b>{{ displayLatest }}</b> 集</span>
              <span v-if="detail.total_episodes > 0 && detail.total_episodes !== displayLatest" class="dim">共 {{ detail.total_episodes }} 集</span>
            </div>

            <p class="overview">{{ displayOverview }}</p>

            <div v-if="detail.genre" class="genres">
              <span v-for="g in detail.genre.split(',')" :key="g" class="g-tag">{{ g }}</span>
            </div>

            <!-- TMDB ID -->
            <div class="path-row">
              <label>🎬 TMDB ID</label>
              <div v-if="!editingTmdb" class="path-val">
                <span>{{ detail.tmdb_id || '未关联' }}</span>
                <button class="btn btn-ghost btn-sm" @click="startEditTmdb">改</button>
              </div>
              <div v-else class="path-edit">
                <input v-model.number="newTmdbId" type="number" placeholder="TMDB ID" />
                <button class="btn btn-primary btn-sm" :disabled="savingTmdb" @click="handleSaveTmdb">保存</button>
                <button class="btn btn-ghost btn-sm" @click="editingTmdb = false">取消</button>
              </div>
            </div>

            <!-- Path -->
            <div class="path-row">
              <label>📂 115 路径</label>
              <div v-if="!editingPath" class="path-val">
                <span>{{ detail.path_115 || '未设置' }}</span>
                <button class="btn btn-ghost btn-sm" @click="editingPath = true">改</button>
              </div>
              <div v-else class="path-edit">
                <input v-model="newPath" type="text" />
                <button class="btn btn-primary btn-sm" :disabled="savingPath" @click="handleSavePath">保存</button>
                <button class="btn btn-ghost btn-sm" @click="editingPath = false">取消</button>
              </div>
            </div>

            <!-- Actions -->
            <div class="actions">
              <button class="btn btn-outline btn-sm" :disabled="syncing" @click="handleSync">
                <span v-if="syncing" class="spinner"></span>
                <span v-else>🔄 同步</span>
              </button>
              <button class="btn btn-primary btn-sm" @click="handleGoShare">📤 转存</button>
              <button class="btn btn-ghost btn-sm" @click="handleDelete">🗑</button>
            </div>
          </div>

          <!-- Right column: Episodes -->
          <div class="modal-right">
            <!-- Season tabs -->
            <div v-if="seasons.length > 1" class="season-bar">
              <button
                v-for="sn in seasons" :key="sn"
                :class="['s-tab', { active: activeSeason === sn }]"
                @click="activeSeason = sn"
              >S{{ sn }}</button>
            </div>

            <div v-if="loadingEps" class="loading-hint"><div class="spinner"></div></div>

            <div v-else-if="currentEpisodes.length > 0" class="ep-grid">
              <EpisodeThumb
                v-for="ep in currentEpisodes"
                :key="`S${ep.season_number}E${ep.episode_number}`"
                :episode-number="ep.episode_number"
                :title="ep.name"
                :still-url="ep.still_path"
                :air-date="ep.air_date"
                :cached-file="ep.cached_file ? {
                  filename: ep.cached_file.filename,
                  file_size: ep.cached_file.file_size,
                  fid: ep.cached_file.fid
                } : null"
              />
            </div>
            <div v-else class="empty-eps">
              <p>暂无剧集数据</p>
              <p class="sub">点击「同步」按钮获取</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.modal-overlay {
  position: fixed; inset: 0; z-index: 1000;
  background: rgba(0,0,0,0.6); backdrop-filter: blur(4px);
  display: flex; align-items: center; justify-content: center;
  padding: 20px;
}

.modal-card {
  width: 85vw; max-width: 1100px; height: 85vh;
  background: var(--bg-secondary);
  border-radius: var(--radius-xl);
  border: 1px solid var(--border);
  overflow: hidden;
  display: flex; flex-direction: column;
  position: relative;
  box-shadow: 0 24px 80px rgba(0,0,0,0.5);
}

.modal-body {
  display: flex; flex: 1; min-height: 0;
  margin-top: -50px; position: relative; z-index: 1;
}

.modal-right {
  flex: 1; overflow-y: auto; min-height: 0;
  padding: 16px 20px 20px 0;
}

.modal-left {
  width: 280px; flex-shrink: 0; overflow-y: auto;
  padding: 16px 24px 20px;
  display: flex; flex-direction: column; gap: 8px;
}

.close-btn {
  position: absolute; top: 12px; right: 12px; z-index: 10;
  width: 32px; height: 32px; border: none; border-radius: 50%;
  background: rgba(0,0,0,0.5); color: #fff; font-size: 14px; cursor: pointer;
}

.modal-bg { height: 200px; flex-shrink: 0; position: relative; overflow: hidden; }
@media (max-width: 768px) { .modal-bg { height: 160px; } }
.modal-bg img { width: 100%; height: 100%; object-fit: cover; transition: opacity .3s ease; }
.bg-gradient { position: absolute; inset: 0; background: linear-gradient(to top, var(--bg-secondary) 0%, transparent 50%, rgba(0,0,0,0.1) 100%); }

.modal-body {
  display: flex; flex: 1; overflow: hidden;
  margin-top: -50px; position: relative; z-index: 1;
}

/* Left */
.modal-left {
  width: 280px; flex-shrink: 0;
  padding: 16px 24px 20px;
  display: flex; flex-direction: column; gap: 8px;
  overflow-y: auto;
}

.poster { width: 140px; height: 210px; border-radius: var(--radius); object-fit: cover; background: var(--bg-elevated); box-shadow: 0 4px 20px rgba(0,0,0,0.6); }
.poster.placeholder { display: none; align-items: center; justify-content: center; font-size: 48px; }
.poster.placeholder.show { display: flex; }

.modal-left h2 { font-size: 20px; font-weight: 700; }
.orig { font-size: 12px; color: var(--text-muted); }
.tags { display: flex; gap: 4px; }
.tag { font-size: 10px; padding: 2px 6px; border-radius: 10px; background: var(--bg-elevated); color: var(--text-secondary); }
.tag.tracking { background: rgba(91,127,255,0.15); color: var(--accent); }
.tag.completed { background: rgba(52,199,89,0.15); color: var(--success); }

.stats { display: flex; flex-wrap: wrap; gap: 6px; font-size: 11px; color: var(--text-secondary); background: var(--bg-card); padding: 6px 10px; border-radius: var(--radius-sm); }
.stats b { color: var(--text-primary); }
.stats .dim { opacity: 0.5; }

.overview { font-size: 12px; color: var(--text-secondary); line-height: 1.6; max-height: 120px; overflow-y: auto; }
.overview.selected-ep { color: var(--text-primary); }

.genres { display: flex; gap: 3px; flex-wrap: wrap; }
.g-tag { font-size: 9px; padding: 1px 6px; background: var(--bg-card); border-radius: 8px; color: var(--text-muted); }

.path-row { font-size: 11px; }
.path-row label { margin-bottom: 2px; display: block; }
.path-val { display: flex; align-items: center; justify-content: space-between; }
.path-val span { color: var(--accent); font-family: monospace; font-size: 11px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.path-edit { display: flex; gap: 4px; }
.path-edit input { flex: 1; font-size: 11px; padding: 4px 8px; }

.actions { display: flex; gap: 6px; flex-wrap: wrap; padding-top: 6px; border-top: 1px solid var(--border); }

/* Right: episodes */
.modal-right {
  flex: 1; overflow-y: auto;
  padding: 16px 20px 20px 0;
}

.season-bar { display: flex; gap: 3px; overflow-x: auto; padding-bottom: 8px; margin-bottom: 8px; }
.s-tab { padding: 4px 12px; border: 1px solid var(--border); border-radius: 14px; background: transparent; color: var(--text-secondary); font-size: 11px; font-weight: 600; cursor: pointer; white-space: nowrap; transition: all var(--transition); }
.s-tab.active { background: var(--accent); border-color: var(--accent); color: #fff; }
.s-tab:hover:not(.active) { border-color: var(--accent); color: var(--accent); }

.loading-hint { display: flex; justify-content: center; padding: 40px; }

.ep-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 8px;
  align-content: start;
}

.empty-eps { text-align: center; padding: 40px; color: var(--text-muted); font-size: 13px; }
.empty-eps .sub { font-size: 12px; margin-top: 4px; }

/* Mobile: fullscreen slide-over */
@media (max-width: 768px) {
  .modal-overlay { padding: 0; align-items: stretch; }
  .modal-card {
    width: 100vw; height: 100vh; max-width: none;
    border-radius: 0; animation: slideIn .3s ease;
    overflow-y: auto;
  }
  @keyframes slideIn { from { transform: translateX(100%) } to { transform: translateX(0) } }
  .modal-body { flex-direction: column; overflow-y: auto; min-height: 0; flex: 1; }
  .modal-left { width: 100%; padding: 12px 16px; overflow: visible; }
  .modal-right { padding: 12px 16px; overflow: visible; min-height: 0; }
  .ep-grid { grid-template-columns: repeat(3, 1fr); gap: 6px; }
  .detail-panel { overflow-y: auto; -webkit-overflow-scrolling: touch; }
}

/* iPad */
@media (min-width: 769px) and (max-width: 1024px) {
  .modal-card { width: 92vw; }
  .modal-left { width: 220px; }
}
</style>
