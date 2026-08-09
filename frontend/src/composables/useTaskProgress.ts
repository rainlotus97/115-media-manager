import { ref } from 'vue'

const visible = ref(false)
const stage = ref('')
const current = ref(0)
const total = ref(0)
const error = ref('')

export function useTaskProgress() {
  function start(label: string) {
    visible.value = true
    stage.value = label
    current.value = 0
    total.value = 0
    error.value = ''
  }
  function update(nextStage: string, cur: number, tot: number) {
    if (nextStage) stage.value = nextStage
    current.value = cur
    total.value = tot
  }
  function finish() {
    visible.value = false
  }
  function fail(message: string) {
    error.value = message
    stage.value = message
    visible.value = true
  }
  return { visible, stage, current, total, error, start, update, finish, fail }
}
