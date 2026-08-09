import { ref } from 'vue'

const expired = ref(false)

export function useSessionEvents() {
  return {
    expired,
    trigger() { expired.value = true },
    dismiss() { expired.value = false },
  }
}
