import { ref } from 'vue'
import type { Toast, ToastType } from '../types'

const toasts = ref<Toast[]>([])
let nextId = 0
const DURATION = 3000

export function useToast() {
  function show(message: string, type: ToastType = 'info') {
    const id = nextId++
    toasts.value = [...toasts.value, { id, message, type }]
    setTimeout(() => {
      toasts.value = toasts.value.filter((t) => t.id !== id)
    }, DURATION)
  }

  function dismiss(id: number) {
    toasts.value = toasts.value.filter((t) => t.id !== id)
  }

  return { toasts, show, dismiss }
}
