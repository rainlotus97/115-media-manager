<script setup lang="ts">
import type { ActivePage } from '../types'
defineProps<{ activePage: ActivePage; compact: boolean }>()
const emit = defineEmits<{ navigate: [page: ActivePage] }>()
const items: { page: ActivePage; icon: string; label: string }[] = [
  { page: 'library', icon: '▦', label: '资源库' },
  { page: 'import', icon: '↓', label: '导入资源' },
  { page: 'cloud-download', icon: '↧', label: '云下载' },
  { page: 'settings', icon: '⚙', label: '设置' },
]
</script>
<template>
  <aside class="sidebar" :class="{ compact }">
    <div class="brand"><b>115</b><span v-if="!compact">资源管理器</span></div>
    <nav>
      <button v-for="item in items" :key="item.page" :title="item.label" :class="{ active: activePage === item.page }" @click="emit('navigate', item.page)">
        <span>{{ item.icon }}</span><em v-if="!compact">{{ item.label }}</em>
      </button>
    </nav>
  </aside>
</template>
<style scoped>
.sidebar { position: fixed; inset: 0 auto 0 0; width: 236px; padding: 18px 12px; border-right: 1px solid var(--border); background: var(--bg-secondary); z-index: 5; }
.sidebar.compact { width: 72px; padding-inline: 10px; }
.brand { height: 42px; display:flex; align-items:center; gap:10px; padding:0 10px 20px; font-size:15px; white-space:nowrap; }
.brand b { display:grid; place-items:center; width:28px; height:28px; background:var(--accent); color:#fff; border-radius:6px; font-size:12px; }
nav { display:grid; gap:4px; }
button { width:100%; height:40px; display:flex; align-items:center; gap:12px; padding:0 10px; border:0; border-radius:6px; background:transparent; color:var(--text-secondary); cursor:pointer; font-size:14px; text-align:left; }
button:hover { background:var(--bg-card-hover); color:var(--text-primary); }
button.active { background:var(--accent-glow); color:var(--accent); font-weight:650; }
button span { width:20px; text-align:center; font-size:18px; } em { font-style:normal; white-space:nowrap; }
.compact button { justify-content:center; padding:0; }
</style>
