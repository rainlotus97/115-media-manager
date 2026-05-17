<script setup lang="ts">
import { ref } from 'vue'
import { useShareBrowsing } from '../composables/useShareBrowsing'
import { useToast } from '../composables/useToast'
import { api } from '../api'

const props = defineProps<{
  presetPath?: string
  embedMode?: boolean
}>()

const emit = defineEmits<{
  saved: [path: string]
}>()

const { state, selectedCount, totalCount, allSelected, isSelected, getFid, fetchInfo, toggleSelectAll, toggleFile, browseTo, browseToFolder, browseUp, reset } = useShareBrowsing()
const { show: toast } = useToast()

const url = ref('')
const password = ref('')
const saving = ref(false)

if (props.presetPath) {
  state.targetPath = props.presetPath
}

async function handleCheck() {
  const u = url.value.trim()
  if (!u) { toast('请先输入分享链接', 'error'); return }
  reset()
  try {
    await fetchInfo(u, password.value.trim())
  } catch (e: any) {
    toast(e.message || '请求失败', 'error')
  }
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter') handleCheck()
}

async function handleSave() {
  if (!state.shareCode || saving.value) return
  const fileIds = Array.from(state.selectedFileIds).join(',')
  const targetPath = state.targetPath.trim() || '资源库/115转存/' + (state.title || '未命名')

  saving.value = true
  try {
    const res = await api.saveFiles({
      url: state.url,
      password: state.password,
      target_path: targetPath,
      file_ids: fileIds,
    })
    if (res.ok) {
      toast(`已转存到: ${targetPath}`, 'success')
      emit('saved', targetPath)
    } else {
      toast(res.error || '转存失败', 'error')
    }
  } catch (e: any) {
    toast('请求失败: ' + e.message, 'error')
  } finally {
    saving.value = false
  }
}

function formatSize(bytes: number): string {
  if (!bytes) return ''
  const mb = bytes / (1024 * 1024)
  return mb >= 1 ? mb.toFixed(1) + ' MB' : (bytes / 1024).toFixed(0) + ' KB'
}
</script>

<template>
  <div class="share-tool" :class="{ embed: embedMode }">
    <template v-if="!embedMode">
      <h1 class="page-title">转存工具</h1>
      <p class="page-desc">粘贴 115 分享链接，选择性转存文件到你的网盘</p>
    </template>

    <!-- Input -->
    <div class="input-card">
      <div class="input-row">
        <input
          v-model="url"
          type="url"
          placeholder="粘贴 115 分享链接... https://115cdn.com/s/xxxx"
          class="url-input"
          @keydown="handleKeydown"
        />
      </div>
      <div class="input-row-sub">
        <input
          v-model="password"
          type="text"
          placeholder="访问码（可选）"
          class="pwd-input"
        />
        <button class="btn btn-primary" @click="handleCheck" :disabled="state.loading">
          <span v-if="state.loading" class="spinner"></span>
          <span v-else>🔍 检查</span>
        </button>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="state.loading" class="loading-card">
      <div class="spinner"></div>
      <span>正在检查链接...</span>
    </div>

    <!-- Share Info -->
    <div v-if="state.hasData && !state.loading" class="result-card">
      <!-- Meta -->
      <div class="share-meta">
        <h3>📁 {{ state.title || '分享内容' }}</h3>
        <div class="meta-tags">
          <span class="meta-tag">📦 {{ state.fileCount }} 项</span>
          <span class="meta-tag">💾 {{ state.sizeStr }}</span>
          <span class="meta-tag">👤 {{ state.userName }}</span>
          <span :class="['badge', state.isExpired ? 'badge-danger' : 'badge-success']">
            {{ state.isExpired ? '❌ 已过期' : '✅ 有效' }}
          </span>
        </div>
        <div v-if="state.isExpired" class="expired-warn">
          ⚠️ 该分享链接已过期，无法转存
        </div>
      </div>

      <!-- Breadcrumb -->
      <div v-if="state.breadcrumbs.length > 1" class="breadcrumb">
        <button class="btn btn-sm btn-ghost" @click="browseUp()">← 返回</button>
        <span class="sep">/</span>
        <template v-for="(b, i) in state.breadcrumbs" :key="b.cid">
          <button
            v-if="i < state.breadcrumbs.length - 1"
            class="btn btn-sm btn-ghost"
            @click="browseTo(b.cid)"
          >
            {{ b.name }}
          </button>
          <span v-else class="current">{{ b.name }}</span>
          <span v-if="i < state.breadcrumbs.length - 1" class="sep">/</span>
        </template>
      </div>

      <!-- File List -->
      <div class="file-list">
        <!-- Select All -->
        <div class="file-row select-all-row">
          <label>
            <input
              type="checkbox"
              :checked="allSelected"
              @change="toggleSelectAll(($event.target as HTMLInputElement).checked)"
            />
            <span class="select-label">全选 / 取消</span>
          </label>
        </div>

        <div
          v-for="f in state.files"
          :key="getFid(f)"
          class="file-row"
          :class="{ folder: f.is_dir }"
        >
          <label>
            <input
              type="checkbox"
              :checked="isSelected(f)"
              @change="toggleFile(getFid(f))"
            />
            <span class="file-icon">{{ f.is_dir ? '📁' : '📄' }}</span>
            <span
              v-if="f.is_dir"
              class="file-name folder-link"
              @click.stop="browseToFolder(getFid(f), f.name)"
            >
              {{ f.name }}
            </span>
            <span v-else class="file-name">{{ f.name }}</span>
            <span v-if="!f.is_dir" class="file-size">{{ formatSize(f.size) }}</span>
            <span v-if="f.is_dir" class="enter-hint">↪ 进入</span>
          </label>
        </div>
      </div>

      <!-- Save Panel -->
      <div v-if="!state.isExpired" class="save-panel">
        <div class="save-path-row">
          <label>📂 保存到目录</label>
          <input
            v-model="state.targetPath"
            type="text"
            placeholder="资源库/115转存/目录名称"
            class="path-input"
          />
        </div>
        <button
          class="btn btn-success btn-block"
          :disabled="saving || selectedCount === 0"
          @click="handleSave"
        >
          <span v-if="saving" class="spinner"></span>
          <span v-else>
            📥 转存{{ selectedCount === totalCount ? '全部' : '选中' }}
            {{ selectedCount }} 项
          </span>
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.share-tool {
  max-width: 700px;
}

.share-tool.embed {
  max-width: none;
}

.page-title {
  font-size: 24px;
  font-weight: 700;
  margin-bottom: 6px;
}

.page-desc {
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 20px;
}

.input-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 20px;
  margin-bottom: 16px;
}

.input-row {
  margin-bottom: 10px;
}

.url-input,
.pwd-input {
  background: var(--bg-input);
  border: 1.5px solid var(--border);
  border-radius: var(--radius);
  color: var(--text-primary);
  font-size: 14px;
  padding: 12px 14px;
  outline: none;
  transition: border-color var(--transition);
  width: 100%;
}

.url-input:focus,
.pwd-input:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-glow);
}

.input-row-sub {
  display: flex;
  gap: 10px;
}

.input-row-sub input {
  flex: 1;
}

.loading-card {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 40px;
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border);
  color: var(--text-secondary);
}

.result-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 24px;
}

.share-meta {
  margin-bottom: 16px;
}

.share-meta h3 {
  font-size: 18px;
  font-weight: 700;
  margin-bottom: 10px;
}

.meta-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.meta-tag {
  font-size: 12px;
  padding: 3px 10px;
  background: var(--bg-elevated);
  border-radius: 20px;
  color: var(--text-secondary);
}

.badge {
  font-size: 12px;
  padding: 3px 10px;
  border-radius: 20px;
  font-weight: 600;
}

.badge-success {
  background: rgba(52, 199, 89, 0.15);
  color: var(--success);
}

.badge-danger {
  background: rgba(255, 69, 58, 0.15);
  color: var(--danger);
}

.expired-warn {
  margin-top: 10px;
  padding: 8px 14px;
  background: rgba(255, 69, 58, 0.1);
  border-radius: var(--radius-sm);
  font-size: 13px;
  color: var(--danger);
}

.breadcrumb {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-bottom: 12px;
  font-size: 13px;
  flex-wrap: wrap;
}

.breadcrumb .sep {
  color: var(--text-muted);
}

.breadcrumb .current {
  font-weight: 600;
  color: var(--text-primary);
}

.file-list {
  max-height: 360px;
  overflow-y: auto;
  margin-bottom: 16px;
}

.file-row {
  padding: 4px 0;
  border-bottom: 1px solid var(--border-light);
}

.file-row:last-child {
  border-bottom: none;
}

.file-row label {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  font-size: 13px;
  color: var(--text-primary);
  margin-bottom: 0;
  font-weight: 400;
}

.select-all-row {
  background: rgba(91, 127, 255, 0.06);
  border-radius: var(--radius-sm);
  padding: 6px 8px !important;
  margin-bottom: 6px;
}

.select-all-row label {
  font-weight: 600;
}

.select-label {
  font-weight: 600;
}

.file-icon {
  font-size: 16px;
  flex-shrink: 0;
}

.file-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.folder-link {
  color: var(--accent);
  cursor: pointer;
  padding: 2px 4px;
  border-radius: 4px;
}

.folder-link:hover {
  background: rgba(91, 127, 255, 0.1);
}

.file-size {
  font-size: 12px;
  color: var(--text-muted);
  flex-shrink: 0;
}

.enter-hint {
  font-size: 12px;
  color: var(--text-muted);
  flex-shrink: 0;
}

.save-panel {
  padding: 16px;
  background: rgba(52, 199, 89, 0.06);
  border: 1px solid rgba(52, 199, 89, 0.15);
  border-radius: var(--radius);
}

.save-path-row {
  margin-bottom: 12px;
}

.path-input {
  background: var(--bg-input);
  border: 1.5px solid var(--border);
  border-radius: var(--radius);
  color: var(--text-primary);
  font-size: 14px;
  padding: 10px 14px;
  outline: none;
  width: 100%;
}

.path-input:focus {
  border-color: var(--success);
}
</style>
