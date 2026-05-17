<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useMedia } from '../composables/useMedia'
import MediaCard from './MediaCard.vue'
import MediaDetail from './MediaDetail.vue'
import type { ActivePage, WatchlistItem } from '../types'

const emit = defineEmits<{
  navigate: [page: ActivePage, status?: string]
}>()

const { items, fetchList } = useMedia()
const loading = ref(true)

const detailItem = ref<WatchlistItem | null>(null)
const showDetail = ref(false)

onMounted(async () => {
  await fetchList()
  loading.value = false
})

// Stats
const trackingCount = computed(() => items.value.filter(i => i.status === 'tracking').length)
const needsUpdateCount = computed(() =>
  items.value.filter(i => i.total_episodes > 0 && i.cached_episodes < i.total_episodes).length
)
const completedCount = computed(() => items.value.filter(i => i.status === 'completed').length)

// Items needing updates
const needsUpdate = computed(() =>
  items.value
    .filter(i => i.total_episodes > 0 && i.cached_episodes < i.total_episodes && i.status === 'tracking')
    .sort((a, b) => {
      const aGap = a.total_episodes - a.cached_episodes
      const bGap = b.total_episodes - b.cached_episodes
      return bGap - aGap // most missing first
    })
)

// Recent additions
const recentItems = computed(() =>
  [...items.value]
    .sort((a, b) => (b.created_at || '').localeCompare(a.created_at || ''))
    .slice(0, 6)
)

function openDetail(item: WatchlistItem) {
  detailItem.value = item
  showDetail.value = true
}

function closeDetail() {
  showDetail.value = false
  detailItem.value = null
  fetchList() // refresh
}

function handleNavigateShare(_path: string) {
  emit('navigate', 'share-link')
}
</script>

<template>
  <div class="dashboard">
    <!-- Hero (compact if already have items) -->
    <section class="hero-banner" :class="{ compact: items.length > 0 }">
      <div class="hero-overlay"></div>
      <div class="hero-content">
        <h1 class="hero-title">{{ items.length > 0 ? '追更看板' : '你的媒体追更好帮手' }}</h1>
        <p v-if="items.length === 0" class="hero-desc">追踪动漫、电影、电视剧更新，结合 115 网盘一键转存</p>
        <div v-if="items.length === 0" class="hero-actions">
          <button class="btn btn-primary" @click="emit('navigate', 'anime')">📺 开始追番</button>
          <button class="btn btn-outline" @click="emit('navigate', 'movies')">🎬 追影追剧</button>
        </div>
      </div>
    </section>

    <!-- Loading -->
    <div v-if="loading" class="loading-state">
      <div class="spinner"></div>
    </div>

    <template v-else-if="items.length > 0">
      <!-- Stats -->
      <section class="stats-row">
        <div class="stat-card" @click="emit('navigate', 'anime', 'tracking')">
          <div class="stat-icon">📺</div>
          <div class="stat-info">
            <div class="stat-value">{{ trackingCount }}</div>
            <div class="stat-label">追更中</div>
          </div>
        </div>
        <div class="stat-card highlight" @click="emit('navigate', 'anime')">
          <div class="stat-icon">📥</div>
          <div class="stat-info">
            <div class="stat-value accent">{{ needsUpdateCount }}</div>
            <div class="stat-label">待更新</div>
          </div>
        </div>
        <div class="stat-card" @click="emit('navigate', 'anime', 'completed')">
          <div class="stat-icon">✅</div>
          <div class="stat-info">
            <div class="stat-value">{{ completedCount }}</div>
            <div class="stat-label">已完结</div>
          </div>
        </div>
      </section>

      <!-- Needs Update -->
      <section v-if="needsUpdate.length > 0" class="section">
        <h2 class="section-title">📥 待更新</h2>
        <div class="card-row">
          <MediaCard
            v-for="item in needsUpdate"
            :key="item.id"
            :item="item"
            @click="openDetail(item)"
          />
        </div>
      </section>

      <!-- Recent -->
      <section class="section">
        <h2 class="section-title">🕐 最近添加</h2>
        <div class="card-row">
          <MediaCard
            v-for="item in recentItems"
            :key="item.id"
            :item="item"
            @click="openDetail(item)"
          />
        </div>
      </section>
    </template>

    <!-- Empty (no items at all) -->
    <section v-if="!loading && items.length === 0" class="section">
      <div class="empty-hint">
        <p>还没有添加任何追剧内容</p>
        <p class="sub">点击上方按钮开始添加你的第一部追剧吧</p>
      </div>
    </section>

    <!-- Detail Panel -->
    <MediaDetail
      v-if="showDetail && detailItem"
      :item="detailItem"
      @close="closeDetail"
      @navigate-share="handleNavigateShare"
    />
  </div>
</template>

<style scoped>
.dashboard {
  max-width: 1200px;
}

.hero-banner {
  position: relative;
  background: linear-gradient(135deg, var(--bg-card) 0%, var(--bg-elevated) 100%);
  border-radius: var(--radius-xl);
  padding: 48px 40px;
  margin-bottom: 32px;
  border: 1px solid var(--border);
  overflow: hidden;
}

.hero-banner.compact {
  padding: 28px 32px;
  margin-bottom: 24px;
}

.hero-overlay {
  position: absolute;
  top: -50%;
  right: -20%;
  width: 400px;
  height: 400px;
  background: var(--accent);
  border-radius: 50%;
  filter: blur(100px);
  opacity: 0.1;
}

.hero-content { position: relative; z-index: 1; }

.hero-title { font-size: 28px; font-weight: 700; margin-bottom: 8px; }
.compact .hero-title { font-size: 22px; margin-bottom: 0; }

.hero-desc { color: var(--text-secondary); font-size: 15px; margin-bottom: 24px; }
.hero-actions { display: flex; gap: 12px; flex-wrap: wrap; }

.loading-state {
  display: flex;
  justify-content: center;
  padding: 64px;
}

.stats-row {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  margin-bottom: 32px;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 20px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  cursor: pointer;
  transition: all var(--transition);
}

.stat-card:hover {
  background: var(--bg-card-hover);
  border-color: var(--accent);
}

.stat-card.highlight {
  border-color: rgba(255, 159, 10, 0.3);
  background: rgba(255, 159, 10, 0.05);
}

.stat-icon { font-size: 32px; }
.stat-value { font-size: 22px; font-weight: 700; }
.stat-value.accent { color: var(--warning); }
.stat-label { font-size: 13px; color: var(--text-secondary); }

.section { margin-bottom: 32px; }
.section-title { font-size: 18px; font-weight: 700; margin-bottom: 16px; }

.card-row {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 14px;
}

.empty-hint {
  text-align: center;
  padding: 48px 20px;
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  border: 1px dashed var(--border);
  color: var(--text-secondary);
  font-size: 14px;
}

.empty-hint .sub {
  font-size: 13px;
  color: var(--text-muted);
  margin-top: 6px;
}

@media (max-width: 768px) {
  .hero-banner { padding: 32px 20px; }
  .hero-title { font-size: 22px; }
  .stats-row { grid-template-columns: repeat(3, 1fr); gap: 8px; }
  .stat-card { padding: 14px; gap: 8px; }
  .stat-icon { font-size: 24px; }
  .stat-value { font-size: 18px; }
  .card-row {
    grid-template-columns: repeat(2, 1fr);
    gap: 10px;
  }
}
</style>
