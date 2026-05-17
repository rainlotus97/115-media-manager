<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api } from '../api'
import { useToast } from '../composables/useToast'

const { show: toast } = useToast()
const magnetLink = ref('')
const targetPath = ref('')
const loading = ref(false)
const tasks = ref<any[]>([])
const loadingTasks = ref(false)

async function handleDownload() {
  if (!magnetLink.value.trim()) {
    toast('请粘贴磁力链接或下载地址', 'error')
    return
  }
  loading.value = true
  try {
    const res = await api.addCloudDownload(
      magnetLink.value.trim(),
      targetPath.value.trim() || undefined
    )
    if (res.ok) {
      toast('已添加下载任务' + (res.task_id ? ` (${res.task_id})` : ''), 'success')
      magnetLink.value = ''
      targetPath.value = ''
      fetchTasks()
    } else {
      toast(res.error || '添加失败', 'error')
    }
  } catch {
    toast('请求失败', 'error')
  } finally {
    loading.value = false
  }
}

async function fetchTasks() {
  loadingTasks.value = true
  try {
    const res = await api.getDownloadTasks()
    if (res.state) {
      tasks.value = res.tasks || []
    }
  } catch { /* ignore */ }
  finally { loadingTasks.value = false }
}

function statusText(st: number): string {
  const map: Record<number, string> = { 0: '等待中', 1: '下载中', 2: '已完成', 3: '失败' }
  return map[st] || '未知'
}

onMounted(fetchTasks)
</script>

<template>
  <div class="cloud-download-page">
    <div class="page-header">
      <h1>云下载</h1>
      <p>粘贴磁力链接或下载地址，直接添加到 115 网盘离线下载</p>
    </div>

    <div class="download-card">
      <div class="form-group">
        <label>磁力链接 / 下载地址</label>
        <textarea
          v-model="magnetLink"
          rows="3"
          placeholder="magnet:?xt=urn:btih:xxxxx 或 http(s)://..."
        ></textarea>
      </div>
      <div class="form-group">
        <label>保存到目录（可选）</label>
        <input
          v-model="targetPath"
          type="text"
          placeholder="资源库/下载 （留空则保存到根目录）"
        />
      </div>
      <button
        class="btn btn-primary btn-block"
        :disabled="loading"
        @click="handleDownload"
      >
        <span v-if="loading" class="spinner"></span>
        <span v-else>☁️ 开始云下载</span>
      </button>
    </div>

    <!-- Task List -->
    <div class="tasks-section">
      <div class="tasks-header">
        <h3>下载任务</h3>
        <button class="btn btn-ghost btn-sm" @click="fetchTasks" :disabled="loadingTasks">
          🔄 刷新
        </button>
      </div>

      <div v-if="loadingTasks" class="loading-hint">
        <div class="spinner"></div>
      </div>

      <div v-else-if="tasks.length === 0" class="empty-state">
        <div class="empty-icon">📥</div>
        <h3>暂无下载记录</h3>
      </div>

      <div v-else class="task-list">
        <div v-for="t in tasks" :key="t.task_id" class="task-row">
          <div class="task-name">{{ t.name || t.task_id }}</div>
          <div class="task-meta">
            <span :class="['task-status', 'status-' + t.status]">{{ statusText(t.status) }}</span>
            <span v-if="t.status === 1" class="task-percent">{{ t.percent }}%</span>
            <span class="task-size">{{ t.size }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.cloud-download-page {
  max-width: 700px;
}

.page-header {
  margin-bottom: 24px;
}

.page-header h1 {
  font-size: 24px;
  font-weight: 700;
  margin-bottom: 6px;
}

.page-header p {
  font-size: 13px;
  color: var(--text-secondary);
}

.download-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 24px;
  margin-bottom: 24px;
}

.form-group {
  margin-bottom: 16px;
}

.tasks-section {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 20px;
}

.tasks-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.tasks-header h3 {
  font-size: 16px;
  font-weight: 600;
}

.loading-hint {
  display: flex;
  justify-content: center;
  padding: 24px;
}

.empty-state {
  text-align: center;
  padding: 32px 20px;
  color: var(--text-secondary);
}

.empty-icon { font-size: 36px; margin-bottom: 8px; }

.empty-state h3 { font-size: 13px; color: var(--text-muted); }

.task-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.task-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  background: var(--bg-elevated);
  border-radius: var(--radius-sm);
  gap: 12px;
}

.task-name {
  flex: 1;
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.task-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  flex-shrink: 0;
}

.task-status {
  padding: 2px 8px;
  border-radius: 10px;
  font-weight: 500;
}

.status-0 { background: rgba(142,142,154,0.15); color: var(--text-muted); }
.status-1 { background: rgba(91,127,255,0.15); color: var(--accent); }
.status-2 { background: rgba(52,199,89,0.15); color: var(--success); }
.status-3 { background: rgba(255,69,58,0.15); color: var(--danger); }

.task-percent { color: var(--accent); }
.task-size { color: var(--text-muted); }
</style>
