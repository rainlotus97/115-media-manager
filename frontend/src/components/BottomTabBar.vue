<script setup lang="ts">
import type { ActivePage } from '../types'

defineProps<{
  activePage: ActivePage
}>()

const emit = defineEmits<{
  navigate: [page: ActivePage]
}>()

const tabItems: { page: ActivePage; icon: string; label: string }[] = [
  { page: 'dashboard', icon: '🏠', label: '首页' },
  { page: 'anime', icon: '📺', label: '动漫' },
  { page: 'movies', icon: '🎬', label: '电影' },
  { page: 'share-link', icon: '📤', label: '转存' },
  { page: 'cloud-download', icon: '☁️', label: '云下载' },
  { page: 'settings', icon: '⚙️', label: '设置' },
]
</script>

<template>
  <nav class="bottom-bar">
    <button
      v-for="item in tabItems"
      :key="item.page"
      :class="['tab-btn', { active: activePage === item.page }]"
      @click="emit('navigate', item.page)"
    >
      <span class="tab-icon">{{ item.icon }}</span>
      <span class="tab-label">{{ item.label }}</span>
    </button>
  </nav>
</template>

<style scoped>
.bottom-bar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  display: flex;
  justify-content: space-around;
  background: var(--bg-secondary);
  border-top: 1px solid var(--border);
  padding: 6px 0 env(safe-area-inset-bottom, 6px);
  z-index: 100;
}

.tab-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 6px 10px;
  border: none;
  background: transparent;
  color: var(--text-muted);
  font-size: 11px;
  cursor: pointer;
  transition: color var(--transition);
}

.tab-btn.active {
  color: var(--accent);
}

.tab-icon {
  font-size: 20px;
}

.tab-label {
  font-size: 11px;
}
</style>
