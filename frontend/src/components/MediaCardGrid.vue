<script setup lang="ts">
import type { WatchlistItem } from '../types'
import MediaCard from './MediaCard.vue'

defineProps<{
  items: WatchlistItem[]
}>()

const emit = defineEmits<{
  'item-click': [item: WatchlistItem]
}>()
</script>

<template>
  <div v-if="items.length > 0" class="card-grid">
    <MediaCard
      v-for="item in items"
      :key="item.id"
      :item="item"
      @click="emit('item-click', item)"
    />
  </div>
  <div v-else class="empty-grid">
    <div class="empty-icon">🎬</div>
    <h3>暂无内容</h3>
    <p>点击「+ 添加」开始追踪</p>
  </div>
</template>

<style scoped>
.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 16px;
}

.empty-grid {
  text-align: center;
  padding: 64px 20px;
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  border: 1px dashed var(--border);
  color: var(--text-secondary);
}

.empty-icon {
  font-size: 48px;
  margin-bottom: 12px;
}

.empty-grid h3 {
  font-size: 16px;
  color: var(--text-primary);
  margin-bottom: 6px;
}

.empty-grid p {
  font-size: 13px;
}

@media (max-width: 640px) {
  .card-grid {
    grid-template-columns: repeat(2, 1fr);
    gap: 10px;
  }
}
</style>
