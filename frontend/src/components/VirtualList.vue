<script setup lang="ts" generic="T extends Record<string, unknown>">
import { computed, ref } from 'vue'

const props = withDefaults(defineProps<{
  items: T[]
  itemHeight?: number
  height?: number
  keyField?: string
}>(), {
  itemHeight: 45,
  height: 420,
  keyField: 'fid',
})

const scrollTop = ref(0)
const container = ref<HTMLElement | null>(null)
const overscan = 6
const total = computed(() => props.items.length * props.itemHeight)
const start = computed(() => Math.max(0, Math.floor(scrollTop.value / props.itemHeight) - overscan))
const end = computed(() => Math.min(props.items.length, Math.ceil((scrollTop.value + props.height) / props.itemHeight) + overscan))
const visible = computed(() => props.items.slice(start.value, end.value))

function onScroll() {
  if (container.value) scrollTop.value = container.value.scrollTop
}
</script>

<template>
  <div ref="container" class="virtual-list" :style="{ height: height + 'px' }" @scroll.passive="onScroll">
    <div class="virtual-spacer" :style="{ height: total + 'px' }">
      <div
        v-for="(item, index) in visible"
        :key="String(item[keyField] ?? index)"
        class="virtual-row"
        :style="{ top: (start + index) * itemHeight + 'px', height: itemHeight + 'px' }"
      >
        <slot :item="item" :index="start + index" />
      </div>
    </div>
  </div>
</template>

<style scoped>
.virtual-list { position: relative; overflow-y: auto; overscroll-behavior: contain; -webkit-overflow-scrolling: touch; }
.virtual-spacer { position: relative; width: 100%; }
.virtual-row { position: absolute; left: 0; right: 0; }
</style>
