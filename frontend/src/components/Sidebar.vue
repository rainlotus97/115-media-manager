<script setup lang="ts">
import type { ActivePage } from '../types'

defineProps<{
  collapsed: boolean
  activePage: ActivePage
  username: string
}>()

const emit = defineEmits<{
  navigate: [page: ActivePage]
  'toggle-collapse': []
  logout: []
}>()

const navItems: { page: ActivePage; icon: string; label: string }[] = [
  { page: 'dashboard', icon: '🏠', label: '首页' },
  { page: 'anime', icon: '📺', label: '动漫' },
  { page: 'movies', icon: '🎬', label: '电影' },
  { page: 'tv', icon: '📼', label: '电视剧' },
  { page: 'cloud-download', icon: '☁️', label: '云下载' },
  { page: 'share-link', icon: '📤', label: '转存工具' },
  { page: 'settings', icon: '⚙️', label: '设置' },
]
</script>

<template>
  <aside class="sidebar" :class="{ collapsed }">
    <div class="sidebar-header">
      <div class="sidebar-logo" @click="emit('toggle-collapse')">
        <span class="logo-icon">📁</span>
        <span v-if="!collapsed" class="logo-text">115 管家</span>
      </div>
    </div>

    <nav class="sidebar-nav">
      <button
        v-for="item in navItems"
        :key="item.page"
        :class="['nav-item', { active: activePage === item.page }]"
        :title="collapsed ? item.label : undefined"
        @click="emit('navigate', item.page)"
      >
        <span class="nav-icon">{{ item.icon }}</span>
        <span v-if="!collapsed" class="nav-label">{{ item.label }}</span>
      </button>
    </nav>

    <div class="sidebar-footer">
      <div class="user-info" v-if="!collapsed">
        <span class="user-avatar">👤</span>
        <span class="user-name">{{ username }}</span>
      </div>
      <button class="nav-item logout-btn" title="退出登录" @click="emit('logout')">
        <span class="nav-icon">🚪</span>
        <span v-if="!collapsed" class="nav-label">退出</span>
      </button>
    </div>
  </aside>
</template>

<style scoped>
.sidebar {
  position: fixed;
  left: 0;
  top: 0;
  bottom: 0;
  width: 240px;
  background: var(--bg-secondary);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  z-index: 100;
  transition: width var(--transition);
  overflow: hidden;
}

.sidebar.collapsed {
  width: 72px;
}

.sidebar-header {
  padding: 20px 16px;
}

.sidebar-logo {
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  user-select: none;
}

.logo-icon {
  font-size: 28px;
  flex-shrink: 0;
}

.logo-text {
  font-size: 16px;
  font-weight: 700;
  white-space: nowrap;
}

.sidebar-nav {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 0 10px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  border: none;
  border-radius: var(--radius);
  background: transparent;
  color: var(--text-secondary);
  font-size: 14px;
  cursor: pointer;
  transition: all var(--transition);
  white-space: nowrap;
  width: 100%;
  text-align: left;
}

.nav-item:hover {
  background: var(--bg-card-hover);
  color: var(--text-primary);
}

.nav-item.active {
  background: var(--accent);
  color: #fff;
}

.nav-icon {
  font-size: 18px;
  flex-shrink: 0;
  width: 24px;
  text-align: center;
}

.sidebar-footer {
  padding: 12px 10px;
  border-top: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 14px;
  font-size: 13px;
  color: var(--text-secondary);
}

.logout-btn {
  color: var(--text-muted) !important;
}

.logout-btn:hover {
  color: var(--danger) !important;
}

@media (max-width: 1024px) {
  .sidebar {
    width: 72px !important;
  }
}
</style>
