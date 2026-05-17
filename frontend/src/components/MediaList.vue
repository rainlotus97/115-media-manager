<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { useMedia } from '../composables/useMedia'
import MediaCardGrid from './MediaCardGrid.vue'
import AddMediaModal from './AddMediaModal.vue'
import MediaDetail from './MediaDetail.vue'
import type { WatchlistItem } from '../types'

const props = defineProps<{
  mediaType: 'anime' | 'movie' | 'tv'
  initialStatus?: string
}>()

const emit = defineEmits<{
  'navigate-share': [path: string]
}>()

const { items, loading, fetchList } = useMedia()

const region = ref('all')
const status = ref('all')
const showAddModal = ref(false)
const showDetail = ref(false)
const detailItem = ref<WatchlistItem | null>(null)

const titleMap: Record<string, string> = {
  anime: '动漫',
  movie: '电影',
  tv: '电视剧',
}

function load() {
  fetchList(
    props.mediaType,
    region.value !== 'all' ? region.value : undefined,
    status.value !== 'all' ? status.value : undefined
  )
}

onMounted(() => {
  if (props.initialStatus) status.value = props.initialStatus
  load()
})
watch(() => props.mediaType, load)
watch(() => props.initialStatus, (s) => { if (s) status.value = s; load() })
watch([region, status], load)

function handleAdd() {
  showAddModal.value = true
}

function handleAdded(_type: string) {
  showAddModal.value = false
  load()
}

function handleItemClick(item: WatchlistItem) {
  detailItem.value = item
  showDetail.value = true
}

function handleDetailClose() {
  showDetail.value = false
  detailItem.value = null
  load() // refresh list
}
</script>

<template>
  <div class="media-page">
    <div class="page-header">
      <h1>{{ titleMap[mediaType] }}</h1>
      <button class="btn btn-primary btn-sm" @click="handleAdd">+ 添加</button>
    </div>

    <!-- Filter Bar -->
    <div class="filter-bar">
      <select v-model="region" class="filter-select">
        <option value="all">全部地区</option>
        <option value="cn">中国</option>
        <option value="jp">日本</option>
        <option value="west">欧美</option>
      </select>
      <select v-model="status" class="filter-select">
        <option value="all">全部状态</option>
        <option value="tracking">追更中</option>
        <option value="completed">已完结</option>
        <option value="paused">已暂停</option>
      </select>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="loading-state">
      <div class="spinner"></div>
      <span>加载中...</span>
    </div>

    <!-- Grid -->
    <div v-else>
      <MediaCardGrid :items="items" @item-click="handleItemClick" />
    </div>

    <!-- Add Modal -->
    <AddMediaModal
      v-if="showAddModal"
      @close="showAddModal = false"
      @added="handleAdded"
    />

    <!-- Detail Panel -->
    <MediaDetail
      v-if="showDetail && detailItem"
      :item="detailItem"
      @close="handleDetailClose"
      @navigate-share="(path: string) => emit('navigate-share', path)"
    />
  </div>
</template>

<style scoped>
.media-page {
  max-width: 1200px;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
}

.page-header h1 {
  font-size: 24px;
  font-weight: 700;
}

.filter-bar {
  display: flex;
  gap: 10px;
  margin-bottom: 24px;
}

.filter-select {
  padding: 8px 14px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  color: var(--text-primary);
  font-size: 13px;
  outline: none;
  cursor: pointer;
}

.filter-select:focus {
  border-color: var(--accent);
}

.loading-state {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 64px;
  color: var(--text-secondary);
}
</style>
