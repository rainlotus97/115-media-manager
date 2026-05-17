<script setup lang="ts">
import { ref } from 'vue'
import { api } from '../api'
import { useToast } from '../composables/useToast'
import type { TMDBSearchItem, TMDBDetailResponse } from '../types'

const emit = defineEmits<{
  close: []
  added: [mediaType: string]
}>()

const { show: toast } = useToast()

const mediaType = ref<'anime' | 'movie' | 'tv'>('anime')
const query = ref('')
const searching = ref(false)
const results = ref<TMDBSearchItem[]>([])
const searched = ref(false)

const selectedTmdb = ref<TMDBSearchItem | null>(null)
const selectedDetail = ref<TMDBDetailResponse | null>(null)
const loadingDetail = ref(false)
const path115 = ref('')
const adding = ref(false)

const typeLabels: Record<string, string> = { anime: '动漫', movie: '电影', tv: '电视剧' }

async function handleSearch() {
  const q = query.value.trim()
  if (!q) { toast('请输入关键词', 'error'); return }

  searching.value = true
  searched.value = true
  try {
    const res = await api.searchTMDB(q, mediaType.value)
    if (res.ok && res.items) {
      results.value = res.items
      if (res.items.length === 0) toast('未找到结果', 'info')
    } else {
      toast(res.error || '搜索失败', 'error')
      results.value = []
    }
  } catch {
    toast('搜索请求失败', 'error')
  } finally {
    searching.value = false
  }
}

async function selectItem(item: TMDBSearchItem) {
  selectedTmdb.value = item
  loadingDetail.value = true
  selectedDetail.value = null
  path115.value = ''

  try {
    const res = await api.getTMDBDetail(item.tmdb_id, mediaType.value)
    if (res.ok) {
      selectedDetail.value = res
      // 自动识别动画类型
      if (res.genres?.some((g: string) => ['动画', 'Animation', 'アニメ'].includes(g))) {
        mediaType.value = 'anime'
      }
      const title = res.title || item.title
      path115.value = `资源库/${typeLabels[mediaType.value]}/${title}`
    }
  } catch {
    toast('获取详情失败', 'error')
  } finally {
    loadingDetail.value = false
  }
}

async function handleAdd() {
  if (!selectedTmdb.value) return
  if (!path115.value.trim()) { toast('请填写 115 存储路径', 'error'); return }

  const detail = selectedDetail.value
  adding.value = true
  try {
    const res = await api.addWatchlist({
      tmdb_id: selectedTmdb.value.tmdb_id,
      title: detail?.title || selectedTmdb.value.title,
      original_title: detail?.original_title || selectedTmdb.value.original_title,
      media_type: mediaType.value,
      region: detail?.region || '',
      genres: detail?.genres || [],
      poster_url: detail?.poster_url || selectedTmdb.value.poster_url || '',
      backdrop_url: detail?.backdrop_url || '',
      overview: detail?.overview || selectedTmdb.value.overview,
      total_episodes: detail?.total_episodes || 0,
      path_115: path115.value.trim(),
    })
    if (res.ok) {
      toast(`已添加「${selectedTmdb.value.title}」`, 'success')
      emit('added', mediaType.value)
    } else {
      toast(res.error || '添加失败', 'error')
    }
  } catch {
    toast('添加请求失败', 'error')
  } finally {
    adding.value = false
  }
}

function backToSearch() {
  selectedTmdb.value = null
  selectedDetail.value = null
}
</script>

<template>
  <Teleport to="body">
    <div class="modal-overlay" @click.self="emit('close')">
      <div class="modal-card">
        <div class="modal-header">
          <h2>添加追剧</h2>
          <button class="btn btn-ghost btn-sm" @click="emit('close')">✕</button>
        </div>

        <!-- Type Tabs -->
        <div class="type-tabs">
          <button
            v-for="t in (['anime', 'movie', 'tv'] as const)"
            :key="t"
            :class="['type-tab', { active: mediaType === t }]"
            @click="mediaType = t"
          >
            {{ typeLabels[t] }}
          </button>
        </div>

        <!-- Search -->
        <div v-if="!selectedTmdb" class="search-section">
          <div class="search-row">
            <input
              v-model="query"
              type="text"
              :placeholder="`搜索${typeLabels[mediaType]}...`"
              @keydown.enter="handleSearch"
            />
            <button class="btn btn-primary" :disabled="searching" @click="handleSearch">
              <span v-if="searching" class="spinner"></span>
              <span v-else>搜索</span>
            </button>
          </div>

          <!-- Results -->
          <div v-if="searching" class="search-status">
            <div class="spinner"></div>
            <span>搜索中...</span>
          </div>

          <div v-if="results.length > 0" class="result-list">
            <div
              v-for="item in results"
              :key="item.tmdb_id"
              class="result-item"
              @click="selectItem(item)"
            >
              <div class="result-poster">
                <img
                  v-if="item.poster_url"
                  :src="item.poster_url"
                  :alt="item.title"
                />
                <span v-else class="no-poster">🎬</span>
              </div>
              <div class="result-info">
                <div class="result-title">{{ item.title }}</div>
                <div class="result-meta">
                  <span v-if="item.year">{{ item.year }}</span>
                  <span v-if="item.vote_average">⭐ {{ item.vote_average.toFixed(1) }}</span>
                </div>
                <div class="result-overview">{{ item.overview }}</div>
              </div>
            </div>
          </div>

          <div v-if="searched && results.length === 0 && !searching" class="empty-search">
            未找到结果
          </div>
        </div>

        <!-- Detail + Path -->
        <div v-if="selectedTmdb" class="detail-section">
          <button class="btn btn-ghost btn-sm back-btn" @click="backToSearch">
            ← 返回搜索结果
          </button>

          <div v-if="loadingDetail" class="search-status">
            <div class="spinner"></div>
            <span>加载详情...</span>
          </div>

          <div v-if="selectedDetail" class="detail-info">
            <div class="detail-header">
              <img
                v-if="selectedDetail.poster_url"
                :src="selectedDetail.poster_url"
                class="detail-poster"
              />
              <div>
                <h3>{{ selectedDetail.title }}</h3>
                <div class="detail-meta">
                  <span v-if="selectedDetail.year">{{ selectedDetail.year }}</span>
                  <span v-if="selectedDetail.region">{{ selectedDetail.region }}</span>
                  <span>⭐ {{ selectedDetail.vote_average?.toFixed(1) }}</span>
                </div>
                <div class="detail-genres">
                  <span v-for="g in selectedDetail.genres" :key="g" class="genre-tag">{{ g }}</span>
                </div>
                <div v-if="selectedDetail.total_episodes" class="detail-eps">
                  共 {{ selectedDetail.total_episodes }} 集 / {{ selectedDetail.number_of_seasons }} 季
                </div>
              </div>
            </div>
            <p class="detail-overview">{{ selectedDetail.overview }}</p>

            <div class="path-section">
              <label>115 网盘存储路径</label>
              <input
                v-model="path115"
                type="text"
                placeholder="资源库/动漫/番剧名"
              />
            </div>

            <button
              class="btn btn-primary btn-block"
              :disabled="adding"
              @click="handleAdd"
            >
              <span v-if="adding" class="spinner"></span>
              <span v-else>✅ 确认添加</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 20px;
}

.modal-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-xl);
  width: 560px;
  max-width: 100%;
  max-height: 85vh;
  overflow-y: auto;
  padding: 24px;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
}

.modal-header h2 {
  font-size: 18px;
  font-weight: 700;
}

.type-tabs {
  display: flex;
  gap: 4px;
  background: var(--bg-elevated);
  border-radius: var(--radius);
  padding: 4px;
  margin-bottom: 16px;
}

.type-tab {
  flex: 1;
  padding: 8px;
  text-align: center;
  border: none;
  background: transparent;
  border-radius: var(--radius-sm);
  color: var(--text-secondary);
  font-size: 13px;
  cursor: pointer;
  transition: all var(--transition);
}

.type-tab.active {
  background: var(--accent);
  color: #fff;
}

.search-row {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
}

.search-row input {
  flex: 1;
}

.search-status {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 32px;
  color: var(--text-secondary);
}

.result-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 400px;
  overflow-y: auto;
}

.result-item {
  display: flex;
  gap: 12px;
  padding: 12px;
  border-radius: var(--radius);
  cursor: pointer;
  transition: background var(--transition);
  border: 1px solid transparent;
}

.result-item:hover {
  background: var(--bg-card-hover);
  border-color: var(--border);
}

.result-poster {
  width: 60px;
  height: 90px;
  border-radius: var(--radius-sm);
  overflow: hidden;
  flex-shrink: 0;
  background: var(--bg-elevated);
  display: flex;
  align-items: center;
  justify-content: center;
}

.result-poster img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.no-poster {
  font-size: 28px;
}

.result-info {
  flex: 1;
  min-width: 0;
}

.result-title {
  font-weight: 600;
  font-size: 14px;
  margin-bottom: 4px;
}

.result-meta {
  font-size: 12px;
  color: var(--text-muted);
  display: flex;
  gap: 8px;
  margin-bottom: 4px;
}

.result-overview {
  font-size: 12px;
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.empty-search {
  text-align: center;
  padding: 32px;
  color: var(--text-muted);
}

.back-btn {
  margin-bottom: 16px;
}

.detail-info {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.detail-header {
  display: flex;
  gap: 16px;
}

.detail-poster {
  width: 100px;
  height: 150px;
  border-radius: var(--radius);
  object-fit: cover;
  flex-shrink: 0;
  background: var(--bg-elevated);
}

.detail-header h3 {
  font-size: 18px;
  font-weight: 700;
  margin-bottom: 6px;
}

.detail-meta {
  font-size: 13px;
  color: var(--text-secondary);
  display: flex;
  gap: 8px;
  margin-bottom: 6px;
}

.detail-genres {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 6px;
}

.genre-tag {
  font-size: 11px;
  padding: 2px 8px;
  background: var(--bg-elevated);
  border-radius: 20px;
  color: var(--text-secondary);
}

.detail-eps {
  font-size: 13px;
  color: var(--accent);
}

.detail-overview {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.6;
}

.path-section {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
</style>
