<script setup lang="ts">
import { useTaskProgress } from '../composables/useTaskProgress'

const progress = useTaskProgress()
</script>

<template>
  <Transition name="fade">
    <div v-if="progress.visible.value" class="progress-toast">
      <span class="spinner" />
      <div>
        <b>{{ progress.stage.value }}</b>
        <small v-if="progress.total.value">
          {{ progress.current.value }} / {{ progress.total.value }}
        </small>
        <small v-else-if="progress.current.value">已处理 {{ progress.current.value }} 项</small>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.progress-toast { position: fixed; top: calc(12px + env(safe-area-inset-top)); right: 12px; z-index: 180; display: flex; align-items: center; gap: 10px; max-width: min(280px, calc(100vw - 24px)); background: var(--bg-card); border: 1px solid var(--border); border-radius: 10px; padding: 10px 14px; box-shadow: 0 8px 24px rgb(0 0 0 / 0.3); }
.progress-toast div { display: grid; gap: 2px; }
.progress-toast b { font-size: 12px; color: var(--text-primary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.progress-toast small { font-size: 11px; color: var(--text-muted); }
.fade-enter-active, .fade-leave-active { transition: opacity 0.2s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
