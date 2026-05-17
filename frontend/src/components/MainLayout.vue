<script setup lang="ts">
import { ref, computed } from 'vue'
import { useAuth } from '../composables/useAuth'
import Sidebar from './Sidebar.vue'
import BottomTabBar from './BottomTabBar.vue'
import Dashboard from './Dashboard.vue'
import MediaList from './MediaList.vue'
import CloudDownload from './CloudDownload.vue'
import ShareLinkTool from './ShareLinkTool.vue'
import SettingsPage from './SettingsPage.vue'
import type { ActivePage } from '../types'

const { user, logout } = useAuth()

const activePage = ref<ActivePage>('dashboard')
const sidebarCollapsed = ref(false)
const sharePresetPath = ref('')
const mediaFilterStatus = ref<string>('')

function goShareLink(path: string) {
  sharePresetPath.value = path
  activePage.value = 'share-link'
}

function handleDashboardNav(page: ActivePage, status?: string) {
  mediaFilterStatus.value = status || ''
  activePage.value = page
}

const isMobile = computed(() => window.innerWidth < 768)
const showSidebar = computed(() => !isMobile.value)

// Listen for resize
window.addEventListener('resize', () => {
  // reactive update via computed
})

function getMediaType(page: ActivePage): 'anime' | 'movie' | 'tv' | null {
  if (page === 'anime') return 'anime'
  if (page === 'movies') return 'movie'
  if (page === 'tv') return 'tv'
  return null
}

const currentMediaType = computed(() => getMediaType(activePage.value))
</script>

<template>
  <div class="app-shell" :class="{ 'sidebar-collapsed': sidebarCollapsed }">
    <Sidebar
      v-if="showSidebar"
      :collapsed="sidebarCollapsed"
      :active-page="activePage"
      :username="user?.username || ''"
      @navigate="(p: ActivePage) => activePage = p"
      @toggle-collapse="sidebarCollapsed = !sidebarCollapsed"
      @logout="logout"
    />

    <main class="main-content">
      <Dashboard v-if="activePage === 'dashboard'" @navigate="handleDashboardNav" />
      <MediaList
        v-else-if="currentMediaType"
        :media-type="currentMediaType"
        :initial-status="mediaFilterStatus"
        @navigate-share="goShareLink"
      />
      <CloudDownload v-else-if="activePage === 'cloud-download'" />
      <ShareLinkTool v-else-if="activePage === 'share-link'" :preset-path="sharePresetPath" />
      <SettingsPage v-else-if="activePage === 'settings'" />
      <div v-else class="placeholder-page">
        <h2>此功能即将上线</h2>
        <p>直链获取功能正在开发中...</p>
      </div>
    </main>

    <BottomTabBar
      v-if="isMobile"
      :active-page="activePage"
      @navigate="(p: ActivePage) => activePage = p"
    />
  </div>
</template>

<style scoped>
.app-shell {
  display: flex;
  min-height: 100vh;
  background: var(--bg-primary);
}

.main-content {
  flex: 1;
  margin-left: 240px;
  padding: 32px;
  min-height: 100vh;
  transition: margin-left var(--transition);
}

.sidebar-collapsed .main-content {
  margin-left: 72px;
}

.placeholder-page {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: calc(100vh - 64px);
  color: var(--text-muted);
  text-align: center;
}

.placeholder-page h2 {
  font-size: 20px;
  margin-bottom: 8px;
  color: var(--text-secondary);
}

@media (max-width: 1024px) {
  .main-content {
    margin-left: 72px !important;
  }
}

@media (max-width: 768px) {
  .main-content {
    margin-left: 0 !important;
    padding: 16px;
    padding-bottom: 80px;
  }
}
</style>
