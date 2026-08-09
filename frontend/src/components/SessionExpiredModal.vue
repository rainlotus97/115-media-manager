<script setup lang="ts">
const emit = defineEmits<{ close: [] }>()
function goSettings() {
  window.location.hash = '/settings'
  emit('close')
}
</script>

<template>
  <div class="session-mask">
    <div class="session-modal">
      <p class="eyebrow">115 SESSION</p>
      <h2>115 授权已失效</h2>
      <p>部分操作需要重新授权后才能继续，本地资源索引不会丢失。</p>
      <div class="actions">
        <button class="btn btn-ghost" @click="emit('close')">知道了</button>
        <button class="btn btn-primary" @click="goSettings">去扫码授权</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.session-mask { position: fixed; inset: 0; z-index: 200; background: rgb(0 0 0 / 0.55); display: grid; place-items: center; padding: 20px; }
.session-modal { width: min(360px, 100%); background: var(--bg-primary); border: 1px solid var(--border); border-radius: 12px; padding: 22px; box-shadow: 0 16px 50px rgb(0 0 0 / 0.35); }
.eyebrow { font-size: 11px; color: var(--danger); font-weight: 700; margin: 0 0 8px; }
h2 { font-size: 19px; margin: 0 0 8px; }
p:not(.eyebrow) { font-size: 13px; color: var(--text-secondary); line-height: 1.6; margin: 0 0 18px; }
.actions { display: flex; gap: 10px; justify-content: flex-end; }
.actions .btn { min-width: 96px; }
</style>
