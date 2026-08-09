<script setup lang="ts">
import type { ActivePage } from '../types'
defineProps<{ activePage: ActivePage }>()
const emit = defineEmits<{ navigate: [page: ActivePage] }>()
const items: { page: ActivePage; icon: string; label: string }[] = [
  { page: 'library', icon: '▦', label: '资源库' }, { page: 'import', icon: '↓', label: '导入' },
  { page: 'cloud-download', icon: '↧', label: '云下载' }, { page: 'settings', icon: '⚙', label: '设置' },
]
</script>
<template><nav class="bottom-bar"><button v-for="item in items" :key="item.page" :class="{ active: activePage === item.page }" @click="emit('navigate', item.page)"><b>{{ item.icon }}</b><span>{{ item.label }}</span></button></nav></template>
<style scoped>
.bottom-bar { position:fixed; inset:auto 0 0; z-index:10; height:70px; padding-bottom:env(safe-area-inset-bottom); display:flex; background:var(--bg-secondary); border-top:1px solid var(--border); }
button { flex:1; border:0; background:transparent; color:var(--text-muted); display:grid; place-content:center; gap:3px; font-size:11px; } b { font-size:18px; font-weight:500; } button.active { color:var(--accent); }
</style>
