<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  episodeNumber: number
  title: string
  stillUrl: string | null
  airDate: string
  cachedFile: { filename: string; file_size: number; fid: string } | null
  selected?: boolean
}>()

const emit = defineEmits<{
  click: []
}>()

function handleImgError(e: Event) {
  const img = e.currentTarget as HTMLImageElement
  if (!img) return
  img.style.display = 'none'
  const parent = img.parentElement
  if (parent) {
    const placeholder = parent.querySelector('.ep-num-big')
    if (placeholder) placeholder.classList.add('show')
  }
}

const status = computed(() => {
  if (props.cachedFile) return 'cached'
  return 'missing'
})

function formatSize(bytes: number): string {
  if (!bytes) return ''
  const mb = bytes / (1024 * 1024)
  return mb >= 1 ? mb.toFixed(1) + 'MB' : (bytes / 1024).toFixed(0) + 'KB'
}
</script>

<template>
  <div
    :class="['ep-cell', status, { selected }]"
    :title="cachedFile ? cachedFile.filename + ' (' + formatSize(cachedFile.file_size) + ')' : (title || 'E' + episodeNumber)"
    @click="emit('click')"
  >
    <!-- Still / placeholder -->
    <div class="ep-img">
      <img v-if="stillUrl" :src="stillUrl" loading="lazy" @error="handleImgError" />
      <span v-else class="ep-num-big">
        <span class="ep-num-text">{{ episodeNumber }}</span>
        <span class="ep-num-label">EP</span>
      </span>
      <!-- Status dot -->
      <span :class="['dot', status]"></span>
      <!-- Cached indicator overlay -->
      <span v-if="cachedFile" class="check-overlay">✓</span>
    </div>
    <!-- Bottom label -->
    <div class="ep-label">
      <span class="ep-num">E{{ String(episodeNumber).padStart(2, '0') }}</span>
      <span v-if="title" class="ep-name">{{ title }}</span>
    </div>
  </div>
</template>

<style scoped>
.ep-cell {
  border-radius: var(--radius-sm);
  overflow: hidden;
  cursor: pointer;
  transition: all 0.15s ease;
  background: var(--bg-card);
  border: 1px solid transparent;
}

.ep-cell:hover {
  transform: scale(1.03);
  border-color: var(--accent);
  box-shadow: 0 4px 16px rgba(0,0,0,0.3);
}

.ep-cell.selected { border-color: var(--accent); box-shadow: 0 0 0 2px var(--accent-glow); }

.ep-img {
  position: relative;
  aspect-ratio: 16 / 9;
  background: var(--bg-elevated);
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.ep-img img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.ep-num-big {
  display: flex; flex-direction: column; align-items: center; gap: 0;
  background: linear-gradient(135deg, var(--bg-card) 0%, var(--bg-elevated) 100%);
  width: 100%; height: 100%;
  justify-content: center;
}
.ep-num-text { font-size: 36px; font-weight: 800; color: var(--text-muted); line-height: 1; }
.ep-num-label { font-size: 10px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 2px; }

.ep-num-big:not(.show) { display: none; }
.ep-num-big.show { display: flex; }

/* Status dot */
.dot {
  position: absolute;
  top: 6px;
  right: 6px;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  box-shadow: 0 0 4px rgba(0,0,0,0.5);
}

.dot.cached { background: var(--success); }
.dot.unaired { background: var(--text-muted); }
.dot.missing { background: var(--warning); }

/* Check overlay */
.check-overlay {
  position: absolute;
  bottom: 4px;
  left: 4px;
  font-size: 12px;
  background: rgba(52,199,89,0.85);
  color: #fff;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.ep-label {
  padding: 6px 8px 8px;
}

.ep-num {
  font-size: 11px;
  font-weight: 700;
  color: var(--text-secondary);
}

.ep-name {
  display: block;
  font-size: 10px;
  color: var(--text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin-top: 1px;
}
</style>
