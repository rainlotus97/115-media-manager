<script setup lang="ts">
import type { WatchlistItem } from '../types'

defineProps<{
  item: WatchlistItem
}>()

const emit = defineEmits<{
  click: [item: WatchlistItem]
}>()

function getStatusLabel(status: string): string {
  switch (status) {
    case 'tracking': return '追更中'
    case 'completed': return '已完结'
    case 'paused': return '已暂停'
    default: return status
  }
}

function getStatusClass(status: string): string {
  switch (status) {
    case 'tracking': return 'tracking'
    case 'completed': return 'completed'
    case 'paused': return 'paused'
    default: return ''
  }
}

function getRegionLabel(region: string): string {
  switch (region) {
    case 'cn': return '中国'
    case 'jp': return '日本'
    case 'west': return '欧美'
    default: return region ? region.toUpperCase() : ''
  }
}
</script>

<template>
  <div class="media-card" @click="emit('click', item)">
    <!-- Poster -->
    <div class="card-poster">
      <img v-if="item.poster_path" :src="item.poster_path" :alt="item.title" />
      <div v-else class="poster-placeholder">
        <span v-if="item.media_type === 'anime'">📺</span>
        <span v-else-if="item.media_type === 'movie'">🎬</span>
        <span v-else>📼</span>
      </div>

      <!-- Status Badge -->
      <span :class="['status-badge', getStatusClass(item.status)]">
        {{ getStatusLabel(item.status) }}
      </span>

      <!-- Region Badge -->
      <span v-if="item.region" class="region-badge">
        {{ getRegionLabel(item.region) }}
      </span>
    </div>

    <!-- Info -->
    <div class="card-info">
      <h4 class="card-title">{{ item.title }}</h4>

      <!-- Episode Status -->
      <div v-if="item.total_episodes > 0 || item.cached_episodes > 0" class="ep-status-row">
        <span class="ep-latest">已缓存 {{ item.cached_episodes || 0 }} 集</span>
        <span v-if="(item.latest_episode || item.total_episodes) > 0" class="ep-aired">
          已更至 {{ item.latest_episode || item.total_episodes }} 集
        </span>
      </div>

      <!-- Genre tags -->
      <div v-if="item.genre" class="genre-row">
        <span
          v-for="g in item.genre.split(',').slice(0, 3)"
          :key="g"
          class="mini-tag"
        >{{ g }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.media-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  overflow: hidden;
  cursor: pointer;
  transition: all 0.25s ease;
}

.media-card:hover {
  transform: translateY(-4px);
  border-color: var(--accent);
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.4), 0 0 0 1px var(--accent-glow);
}

.card-poster {
  position: relative;
  aspect-ratio: 2 / 3;
  background: var(--bg-elevated);
  overflow: hidden;
}

.card-poster img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform 0.3s ease;
}

.media-card:hover .card-poster img {
  transform: scale(1.05);
}

.poster-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 48px;
  background: linear-gradient(135deg, var(--bg-card) 0%, var(--bg-elevated) 100%);
}

.status-badge {
  position: absolute;
  top: 8px;
  right: 8px;
  font-size: 10px;
  font-weight: 700;
  padding: 3px 8px;
  border-radius: 20px;
  backdrop-filter: blur(8px);
}

.status-badge.tracking {
  background: rgba(91, 127, 255, 0.85);
  color: #fff;
}

.status-badge.completed {
  background: rgba(52, 199, 89, 0.85);
  color: #fff;
}

.status-badge.paused {
  background: rgba(142, 142, 154, 0.7);
  color: #fff;
}

.region-badge {
  position: absolute;
  top: 8px;
  left: 8px;
  font-size: 10px;
  font-weight: 600;
  padding: 3px 8px;
  border-radius: 20px;
  background: rgba(0, 0, 0, 0.6);
  color: #fff;
  backdrop-filter: blur(4px);
}

.card-info {
  padding: 12px 14px 16px;
}

.card-title {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 8px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ep-status-row {
  display: flex;
  gap: 8px;
  margin-bottom: 6px;
  font-size: 11px;
}

.ep-latest {
  color: var(--accent);
  font-weight: 600;
}

.ep-aired {
  color: var(--text-muted);
}

.genre-row {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
  margin-bottom: 6px;
}

.mini-tag {
  font-size: 10px;
  padding: 1px 6px;
  background: rgba(142, 142, 154, 0.15);
  border-radius: 10px;
  color: var(--text-muted);
}


@media (max-width: 768px) {
  .card-info {
    padding: 8px 10px 12px;
  }
  .card-title {
    font-size: 13px;
  }
}
</style>
