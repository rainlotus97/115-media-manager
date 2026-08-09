<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import Sidebar from './Sidebar.vue'
import BottomTabBar from './BottomTabBar.vue'
import ResourceLibrary from './ResourceLibrary.vue'
import ImportPage from './ImportPage.vue'
import CloudDownload from './CloudDownload.vue'
import SettingsPage from './SettingsPage.vue'
import type { ActivePage } from '../types'

const validPages: ActivePage[] = ['library', 'import', 'cloud-download', 'settings']
const activePage = ref<ActivePage>(pageFromHash())
const compact = ref(window.innerWidth < 1024)
const mobile = ref(window.innerWidth < 768)
const refreshKey = ref(0)

function resize() {
  compact.value = window.innerWidth < 1024
  mobile.value = window.innerWidth < 768
}
function pageFromHash(): ActivePage {
  const hash = window.location.hash.replace(/^#\/?/, '') as ActivePage
  return validPages.includes(hash) ? hash : 'library'
}

onMounted(() => window.addEventListener('resize', resize))
onUnmounted(() => window.removeEventListener('resize', resize))
window.addEventListener('hashchange', () => { activePage.value = pageFromHash() })

const showSidebar = computed(() => !mobile.value)
function navigate(page: ActivePage) {
  activePage.value = page
  if (window.location.hash !== `#/${page}`) window.location.hash = `/${page}`
}
function imported() { refreshKey.value++; activePage.value = 'library' }
</script>

<template>
  <div class="app-shell" :class="{ compact }">
    <Sidebar v-if="showSidebar" :compact="compact" :active-page="activePage" @navigate="navigate" />
    <main class="main-content">
      <ResourceLibrary v-show="activePage === 'library'" :key="refreshKey" @import="navigate('import')" />
      <ImportPage v-show="activePage === 'import'" @imported="imported" />
      <CloudDownload v-show="activePage === 'cloud-download'" />
      <SettingsPage v-show="activePage === 'settings'" />
    </main>
    <BottomTabBar v-if="mobile" :active-page="activePage" @navigate="navigate" />
  </div>
</template>

<style scoped>
.app-shell { min-height: 100vh; background: var(--bg-primary); }
.main-content { margin-left: 236px; min-height: 100vh; padding: 28px 32px 48px; }
.compact .main-content { margin-left: 72px; }
@media (max-width: 767px) {
  .main-content,
  .compact .main-content {
    margin-left: 0;
    padding: 18px 16px calc(92px + env(safe-area-inset-bottom));
  }
}
</style>
