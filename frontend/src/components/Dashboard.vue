<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useMedia } from '../composables/useMedia'
import { useCookie } from '../composables/useCookie'
import { useToast } from '../composables/useToast'
import { api } from '../api'
import MediaCard from './MediaCard.vue'
import MediaDetail from './MediaDetail.vue'
import type { ActivePage, WatchlistItem } from '../types'

const emit = defineEmits<{
  navigate: [page: ActivePage, status?: string]
}>()

const { items, fetchList } = useMedia()
const { cookieValid, check: checkCookie } = useCookie()
const { show: toast } = useToast()
const loading = ref(true)
const syncingAll = ref(false)

const detailItem = ref<WatchlistItem | null>(null)
const showDetail = ref(false)

onMounted(async () => {
  await Promise.all([fetchList(), checkCookie()])
  loading.value = false
})

const trackingCount = computed(() => items.value.filter(i => i.status === 'tracking').length)
const needsUpdateCount = computed(() =>
  items.value.filter(i => i.total_episodes > 0 && i.cached_episodes < i.total_episodes).length
)
const completedCount = computed(() => items.value.filter(i => i.status === 'completed').length)

// Recent: last 8 items sorted by last_synced_at or created_at
const recentItems = computed(() =>
  [...items.value].sort((a, b) => (b.last_synced_at || b.created_at || '').localeCompare(a.created_at || '')).slice(0, 8)
)

// Items needing updates
const needsUpdate = computed(() =>
  items.value.filter(i => i.total_episodes > 0 && i.cached_episodes < i.total_episodes && i.status === 'tracking')
    .sort((a, b) => (b.total_episodes - b.cached_episodes) - (a.total_episodes - a.cached_episodes))
)

async function handleSyncAll() {
  syncingAll.value = true
  try {
    const res = await api.syncWatchlistAll() as any
    if (res.ok) {
      const okList = (res.results || []).filter((r: any) => r.result)
      const failList = (res.results || []).filter((r: any) => !r.result)
      if (okList.length > 0) toast(`同步完成 ${okList.length}/${res.total} 部`, 'success')
      if (failList.length > 0) toast(`${failList.length} 部同步失败`, 'error')
    } else {
      toast(res.error || '同步失败', 'error')
    }
    await fetchList()
  } catch { toast('同步请求失败', 'error') }
  finally { syncingAll.value = false }
}

function openDetail(item: WatchlistItem) {
  detailItem.value = item
  showDetail.value = true
}
function closeDetail() { showDetail.value = false; detailItem.value = null; fetchList() }
</script>

<template>
  <div class="dashboard">
    <!-- Cookie alert -->
    <div v-if="cookieValid === false" class="cookie-alert">
      ⚠️ 115 Cookie 无效或已过期，请前往 <a href="#" @click.prevent="emit('navigate', 'settings')">设置页</a> 更新
    </div>

    <!-- Loading skeleton -->
    <div v-if="loading" class="skel-row">
      <div v-for="i in 6" :key="i" class="skel-card skeleton"></div>
    </div>

    <template v-else-if="items.length === 0">
      <!-- Guided empty state -->
      <section class="onboard">
        <div class="onboard-icon">🎬</div>
        <h2>开始构建你的媒体库</h2>
        <p class="onboard-desc">三步开始追踪剧集更新：</p>
        <div class="steps">
          <div class="step">
            <span class="step-num">1</span>
            <div><strong>配置 115 Cookie</strong><p>先进入设置页配置你的 115 网盘 Cookie</p></div>
          </div>
          <div class="step">
            <span class="step-num">2</span>
            <div><strong>获取 TMDB API Key</strong><p>在 themoviedb.org 免费注册获取</p></div>
          </div>
          <div class="step">
            <span class="step-num">3</span>
            <div><strong>添加追剧</strong><p>搜索你想追踪的动漫/电影/电视剧</p></div>
          </div>
        </div>
        <div class="onboard-actions">
          <button class="btn btn-primary" @click="emit('navigate', 'anime')">📺 开始追番</button>
          <button class="btn btn-outline" @click="emit('navigate', 'settings')">⚙️ 去设置</button>
        </div>
      </section>
    </template>

    <template v-else>
      <!-- Header with sync all -->
      <div class="dash-header">
        <h1>追更看板</h1>
        <button class="btn btn-outline btn-sm" :disabled="syncingAll" @click="handleSyncAll">
          <span v-if="syncingAll" class="spinner"></span>
          <span v-else>🔄 一键同步</span>
        </button>
      </div>

      <!-- Stats -->
      <section class="stats-row">
        <div class="stat-card" @click="emit('navigate', 'anime', 'tracking')">
          <div class="stat-icon">📺</div><div class="stat-info">
            <div class="stat-value">{{ trackingCount }}</div><div class="stat-label">追更中</div>
          </div>
        </div>
        <div class="stat-card highlight" @click="emit('navigate', 'anime')">
          <div class="stat-icon">📥</div><div class="stat-info">
            <div class="stat-value accent">{{ needsUpdateCount }}</div><div class="stat-label">待更新</div>
          </div>
        </div>
        <div class="stat-card" @click="emit('navigate', 'anime', 'completed')">
          <div class="stat-icon">✅</div><div class="stat-info">
            <div class="stat-value">{{ completedCount }}</div><div class="stat-label">已完结</div>
          </div>
        </div>
      </section>

      <!-- Needs update -->
      <section v-if="needsUpdate.length > 0" class="section">
        <h2 class="section-title">📥 待更新</h2>
        <div class="card-row"><MediaCard v-for="item in needsUpdate" :key="item.id" :item="item" @click="openDetail(item)" /></div>
      </section>

      <!-- Recent -->
      <section class="section">
        <h2 class="section-title">🕐 最近添加</h2>
        <div class="card-row"><MediaCard v-for="item in recentItems" :key="item.id" :item="item" @click="openDetail(item)" /></div>
      </section>
    </template>

    <MediaDetail v-if="showDetail && detailItem" :item="detailItem" @close="closeDetail" @navigate-share="() => emit('navigate', 'share-link')" />
  </div>
</template>

<style scoped>
.dashboard { max-width: 1200px; }

.cookie-alert {
  padding: 10px 16px; margin-bottom: 16px;
  background: rgba(255,69,58,0.1); border: 1px solid rgba(255,69,58,0.3);
  border-radius: var(--radius); font-size: 13px; color: var(--danger);
}
.cookie-alert a { color: var(--danger); font-weight: 600; text-decoration: underline; }

.dash-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 24px; }
.dash-header h1 { font-size: 24px; font-weight: 700; }

.stats-row { display: grid; grid-template-columns: repeat(3,1fr); gap: 16px; margin-bottom: 32px; }
.stat-card { display: flex; align-items: center; gap: 14px; padding: 20px; background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius-lg); cursor: pointer; transition: all var(--transition); }
.stat-card:hover { background: var(--bg-card-hover); border-color: var(--accent); }
.stat-card.highlight { border-color: rgba(255,159,10,0.3); background: rgba(255,159,10,0.05); }
.stat-icon { font-size: 32px; }
.stat-value { font-size: 22px; font-weight: 700; }
.stat-value.accent { color: var(--warning); }
.stat-label { font-size: 13px; color: var(--text-secondary); }

.section { margin-bottom: 32px; }
.section-title { font-size: 18px; font-weight: 700; margin-bottom: 16px; }
.card-row { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px,1fr)); gap: 14px; }

/* Onboarding */
.onboard { text-align: center; padding: 48px 20px; background: var(--bg-card); border-radius: var(--radius-xl); border: 1px solid var(--border); max-width: 560px; margin: 0 auto; }
.onboard-icon { font-size: 64px; margin-bottom: 16px; }
.onboard h2 { font-size: 24px; margin-bottom: 8px; }
.onboard-desc { color: var(--text-secondary); margin-bottom: 24px; }
.steps { display: flex; flex-direction: column; gap: 16px; margin-bottom: 24px; text-align: left; }
.step { display: flex; align-items: flex-start; gap: 12px; padding: 12px; background: var(--bg-elevated); border-radius: var(--radius); }
.step-num { width: 28px; height: 28px; border-radius: 50%; background: var(--accent); color: #fff; display: flex; align-items: center; justify-content: center; font-weight: 700; flex-shrink: 0; }
.step strong { font-size: 14px; }
.step p { font-size: 12px; color: var(--text-secondary); margin-top: 2px; }
.onboard-actions { display: flex; gap: 10px; justify-content: center; }

@media (max-width: 768px) {
  .stats-row { gap: 8px; }
  .stat-card { padding: 14px; gap: 8px; }
  .stat-icon { font-size: 24px; }
  .stat-value { font-size: 18px; }
  .card-row { grid-template-columns: repeat(2,1fr); gap: 10px; }
}
</style>
