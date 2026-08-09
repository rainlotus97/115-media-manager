<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api } from '../api'
import { useToast } from '../composables/useToast'
import type { ImportPreview, ReceiveRecord, Resource, ResourceFile } from '../types'
import VirtualList from './VirtualList.vue'

const emit = defineEmits<{ imported: [] }>()
const { show: toast } = useToast()
const url = ref('')
const password = ref('')
const preview = ref<ImportPreview | null>(null)
const loading = ref(false)
const saving = ref(false)
const clearingReceive = ref(false)
const receiveConflict = ref<{ message: string; raw?: string; records: ReceiveRecord[] } | null>(null)
const selected = ref(new Set<string>())
const targetPath = ref('')
const selectedResource = ref<number | null>(null)
const resourceOptions = ref<Resource[]>([])
const manualMatched = ref(new Set<string>())

const files = computed(() => preview.value?.files || [])
const matches = computed(() => preview.value?.matches || [])
const autoMatchedIds = computed(() => new Set(matches.value.flatMap(m => m.matched_file_ids)))
const matchedIds = computed(() => new Set([...autoMatchedIds.value, ...manualMatched.value]))
const selectedCount = computed(() => selected.value.size)
const chosenMatch = computed(() => matches.value.find(m => m.resource_id === selectedResource.value) || null)

function size(bytes: number) { return bytes >= 1024 ** 3 ? `${(bytes / 1024 ** 3).toFixed(1)} GB` : `${(bytes / 1024 ** 2).toFixed(1)} MB` }
function toggle(fid: string) { const next = new Set(selected.value); next.has(fid) ? next.delete(fid) : next.add(fid); selected.value = next }
function selectUncached() { selected.value = new Set(files.value.filter(f => f.is_dir || !matchedIds.value.has(f.fid)).map(f => f.fid)) }
function selectAll() { selected.value = new Set(files.value.map(f => f.fid)) }
function resetAll() {
  url.value = ''
  password.value = ''
  preview.value = null
  selected.value = new Set()
  targetPath.value = ''
  selectedResource.value = null
  manualMatched.value = new Set()
}
function parseEpisode(name: string) {
  let m = /[sS](\d{1,2})\s*[eE](\d{1,4})/.exec(name)
  if (m) return { season: Number(m[1]), episode: Number(m[2]) }
  m = /(?:^|[^a-zA-Z])[eE][pP]\.?\s*(\d{1,4})/.exec(name)
  if (m) return { season: 1, episode: Number(m[1]) }
  m = /\[(\d{1,4}(?:\.5)?)\]/.exec(name)
  if (m) return { season: 1, episode: Math.floor(Number(m[1])) }
  m = /第\s*(\d{1,4})\s*(?:集|话|話)/.exec(name)
  if (m) return { season: 1, episode: Number(m[1]) }
  const stem = name.replace(/\.[^.]+$/, '')
  m = /(?:^|\s)(\d{1,4}(?:\.5)?)(?:\s|$)/.exec(stem)
  if (m) {
    const ep = Math.floor(Number(m[1]))
    if (ep >= 1 && ep <= 9999) return { season: 1, episode: ep }
  }
  return null
}

async function inspect() {
  if (!url.value.trim()) { toast('请输入 115 分享链接', 'error'); return }
  loading.value = true
  preview.value = null
  selected.value = new Set()
  selectedResource.value = null
  manualMatched.value = new Set()
  try {
    const result = await api.previewImport(url.value.trim(), password.value.trim())
    preview.value = result
    selectUncached()
    if (result.matches.length === 1) {
      selectedResource.value = result.matches[0].resource_id
      targetPath.value = result.matches[0].path_115
      await applyResourceMatching(result.matches[0].resource_id)
    } else {
      targetPath.value = ''
    }
    selectUncached()
  } catch (error: any) {
    toast(error.data?.error || error.message || '链接解析失败', 'error')
  } finally { loading.value = false }
}

function chooseMatch(match: ImportPreview['matches'][number]) {
  selectedResource.value = match.resource_id
  targetPath.value = match.path_115
  applyResourceMatching(match.resource_id)
}

async function chooseResourceOption(resource: Resource) {
  selectedResource.value = resource.id
  targetPath.value = resource.path_115
  await applyResourceMatching(resource.id)
}

async function applyResourceMatching(resourceId: number) {
  try {
    const detail = await api.getResource(resourceId)
    const cachedExact = new Map<string, true>()
    const cachedEpisodes = new Map<string, true>()
    for (const file of detail.files) {
      if (file.tmdb_valid === 0) continue
      const name = file.display_name || file.filename || file.name || ''
      cachedExact.set(`${name}\u0000${Number(file.file_size ?? file.size ?? 0)}`, true)
      const parsed = parseEpisode(name)
      if (parsed && file.season_number != null && file.episode_number != null) {
        cachedEpisodes.set(`S${parsed.season}E${parsed.episode}`, true)
      } else if (parsed) {
        cachedEpisodes.set(`S${parsed.season}E${parsed.episode}`, true)
      }
    }
    const hit = new Set<string>()
    for (const file of files.value) {
      const name = file.name || ''
      const parsed = parseEpisode(name)
      const byEpisode = parsed && cachedEpisodes.has(`S${parsed.season}E${parsed.episode}`)
      const byExact = cachedExact.has(`${name}\u0000${Number(file.size ?? 0)}`)
      if (byEpisode || byExact) hit.add(file.fid)
    }
    manualMatched.value = hit
    selectUncached()
    toast(`已按“${detail.item.title}”标记 ${hit.size} 个已缓存（含 SxxExx 集数匹配）`, 'info')
  } catch (error: any) {
    toast(error.data?.error || error.message || '读取资源失败', 'error')
  }
}

function clearMatch() {
  selectedResource.value = null
  manualMatched.value = new Set()
  targetPath.value = ''
}

async function save() {
  if (!preview.value || !selectedCount.value) { toast('请选择需要保存的文件', 'error'); return }
  if (!targetPath.value.trim()) { toast('请选择或输入保存目录', 'error'); return }
  saving.value = true
  try {
    const selectedFiles = files.value.filter(f => selected.value.has(f.fid)) as ResourceFile[]
    const result = await api.importFiles({
      url: url.value.trim(),
      password: password.value.trim(),
      title: preview.value.title,
      target_path: targetPath.value.trim() || undefined,
      resource_id: selectedResource.value || undefined,
      file_ids: [...selected.value],
      files: selectedFiles,
    })
    if (!result.ok) throw new Error(result.error || '转存失败')
    toast(`已保存到 ${result.target_path}`, 'success')
    emit('imported')
    resetAll()
  } catch (error: any) {
    if (error.data?.code === 'ALREADY_RECEIVED') {
      receiveConflict.value = {
        message: error.data?.error || error.message || '115 提示这些文件已接收过，请先清理接收记录',
        raw: error.data?.receive_raw || '',
        records: Array.isArray(error.data?.receive_records) ? error.data.receive_records : [],
      }
      return
    }
    toast(error.data?.error || error.message || '转存失败', 'error')
  } finally { saving.value = false }
}

async function clearAndRetry() {
  if (!receiveConflict.value) return
  clearingReceive.value = true
  try {
    const ids = receiveConflict.value.records.map(r => r.id).filter(Boolean)
    if (ids.length) {
      await api.clearReceiveHistory(ids)
      toast(`已清理 ${ids.length} 条接收记录，正在重新保存`, 'info')
    }
    receiveConflict.value = null
    await save()
  } catch (error: any) {
    toast(error.data?.error || error.message || '清理接收记录失败', 'error')
  } finally { clearingReceive.value = false }
}

onMounted(async () => {
  try {
    const result = await api.getResources()
    resourceOptions.value = result.items
  } catch { /* 未授权时静默 */ }
})
</script>

<template>
  <section class="import-page">
    <header><div><p class="eyebrow">IMPORT AND DEDUPE</p><h1>导入资源</h1><p>解析分享链接，自动识别本地索引已有的文件，并复用已记录的 115 目录。</p></div><button class="btn btn-ghost btn-sm" @click="resetAll">重置</button></header>

    <div class="entry">
      <label>115 分享链接<input v-model="url" type="url" placeholder="https://115.com/s/..." @keyup.enter="inspect" /></label>
      <div class="entry-bottom">
        <label>访问码（可选）<input v-model="password" type="text" placeholder="分享访问码" /></label>
        <button class="btn btn-primary" :disabled="loading" @click="inspect"><span v-if="loading" class="spinner" /><span v-else>解析链接</span></button>
      </div>
    </div>

    <template v-if="preview">
      <section class="summary">
        <div><p class="eyebrow">SHARE CONTENT</p><h2>{{ preview.title }}</h2><p>{{ files.length }} 个可保存文件</p></div>
        <div class="match-note" :class="{ matched: matchedIds.size }"><b>{{ matchedIds.size }} 个</b><span>{{ matchedIds.size ? '与资源库索引命中' : '未命中已有资源' }}</span></div>
      </section>

      <section v-if="matches.length" class="reuse">
        <p>检测到已缓存资源。选中一个目标目录后，新增文件将自动保存到该目录。</p>
        <label v-for="match in matches" :key="match.resource_id" class="match-row">
          <input type="radio" :checked="selectedResource === match.resource_id" @change="chooseMatch(match)" />
          <span><b>{{ match.title }}</b><small>{{ match.path_115 }}</small></span>
          <em>{{ match.matched_file_ids.length }} 项已存在</em>
        </label>
        <button class="link-btn" @click="clearMatch">保存到新目录</button>
      </section>

      <section v-if="!chosenMatch && resourceOptions.length" class="destination">
        <p class="section-hint">链接属于已有资源但未自动命中时，可以手动选择源目录并重新标记已缓存文件：</p>
        <label v-for="resource in resourceOptions" :key="resource.id" class="resource-option">
          <input type="radio" :checked="selectedResource === resource.id" @change="chooseResourceOption(resource)" />
          <span><b>{{ resource.title }}</b><small>{{ resource.path_115 }}</small></span>
        </label>
      </section>

      <section class="destination">
        <label>保存到 115 目录（默认沿用源目录，可单独修改）<input v-model="targetPath" type="text" placeholder="例如：资源库/剧集/资源名称" /></label>
        <p>目录不存在时会在 115 网盘中创建。</p>
      </section>

      <section class="files">
        <div class="files-head">
          <div><h2>文件清单</h2><p>选择源目录后按 SxxExx 集数过滤；保存时不修改文件名。</p></div>
          <div class="quick"><button class="link-btn" @click="selectUncached">仅选未缓存</button><button class="link-btn" @click="selectAll">全选</button></div>
        </div>
        <div class="file-table">
          <VirtualList :items="files" :item-height="45" :height="420" key-field="fid">
            <template #default="{ item }">
              <label class="import-file" :class="{ cached: matchedIds.has(item.fid) }">
                <input :checked="selected.has(item.fid)" type="checkbox" @change="toggle(item.fid)" />
                <span class="filename">{{ item.is_dir ? '目录 / ' : '' }}{{ item.name }}</span>
                <small>{{ item.is_dir ? '文件夹' : size(item.size) }}</small>
                <em v-if="matchedIds.has(item.fid)">已缓存</em>
              </label>
            </template>
          </VirtualList>
        </div>
        <footer><span>已选择 {{ selectedCount }} 个文件</span><button class="btn btn-primary" :disabled="saving || !selectedCount" @click="save"><span v-if="saving" class="spinner" /><span v-else>保存到 115</span></button></footer>
      </section>
    </template>

    <div v-if="receiveConflict" class="modal-mask">
      <div class="modal">
        <header><div><h2>115 接收记录冲突</h2><p>这些文件之前在 115 里接收过，即使目标目录已删除，接收记录仍会阻止再次转存。</p></div><button class="modal-close" @click="receiveConflict = null">×</button></header>
        <p class="conflict-message">{{ receiveConflict.message }}</p>
        <p v-if="receiveConflict.raw" class="raw-error">115 原文：{{ receiveConflict.raw }}</p>
        <div v-if="receiveConflict.records.length" class="record-list">
          <div v-for="rec in receiveConflict.records" :key="rec.id" class="record-row">
            <span><b>{{ rec.name }}</b><small>{{ rec.parent_name }}</small></span>
            <em>{{ (rec.file_size / 1024 ** 3).toFixed(1) }} GB</em>
          </div>
          <p class="record-tip">点击“清理并重试”只会删除以上 115 接收记录（不删除任何网盘文件），随后自动重新保存。若清理后仍报“已接收”，说明 115 服务端记住了该分享，通常需要分享者重新生成一个新分享链接。</p>
        </div>
        <p v-else class="record-tip">未能自动匹配到具体接收记录。请在 115 生活 App / 网页端进入「传输 → 接收」，删除或清空对应记录后再重试。</p>
        <footer>
          <button class="btn btn-ghost" @click="receiveConflict = null">取消</button>
          <button v-if="receiveConflict.records.length" class="btn btn-primary" :disabled="clearingReceive || saving" @click="clearAndRetry">
            <span v-if="clearingReceive" class="spinner" /><span v-else>清理并重试</span>
          </button>
          <button v-else class="btn btn-primary" @click="receiveConflict = null">知道了</button>
        </footer>
      </div>
    </div>
  </section>
</template>

<style scoped>
.import-page{max-width:900px;margin:0 auto}.eyebrow{font-size:11px;font-weight:700;color:var(--accent);margin:0 0 7px}h1{margin:0 0 8px;font-size:28px}.import-page>header{display:flex;justify-content:space-between;align-items:start;gap:12px}header>p:last-child{margin:0;color:var(--text-secondary);font-size:14px}.rules-tools{display:flex;gap:8px;flex-wrap:wrap;justify-content:flex-end}.entry,.summary,.reuse,.destination,.files,.rename-rules{margin-top:24px;padding:20px;background:var(--bg-card);border:1px solid var(--border);border-radius:7px}.entry label,.destination label{display:block}.entry-bottom{display:flex;align-items:end;gap:12px;margin-top:14px}.entry-bottom label{flex:1}.entry-bottom .btn{height:43px;min-width:100px}.summary{display:flex;align-items:center;justify-content:space-between}.summary h2,.files h2{font-size:16px;margin:0 0 5px}.summary p:not(.eyebrow),.files p,.destination p,.section-hint{margin:0;color:var(--text-secondary);font-size:12px;line-height:1.5}.match-note{display:grid;text-align:right;color:var(--text-muted);font-size:12px}.match-note b{font-size:22px;font-weight:650}.match-note.matched{color:var(--success)}.reuse p{font-size:13px;margin:0 0 12px;color:var(--text-secondary)}.match-row{display:flex;align-items:center;gap:11px;padding:12px 4px;border-top:1px solid var(--border);cursor:pointer}.match-row span{display:grid;gap:3px;flex:1;font-size:13px}.match-row small{color:var(--text-muted);font:11px ui-monospace,monospace}.match-row em{font-style:normal;color:var(--success);font-size:12px}.link-btn{background:transparent;border:0;color:var(--accent);padding:6px 0;font-size:12px;cursor:pointer}.destination{padding-bottom:16px}.rename-rules{display:grid;gap:8px}.rules-head{display:flex;justify-content:space-between;gap:12px;align-items:start}.rules-head h2{font-size:16px;margin:0 0 4px}.rules-head p{margin:0;color:var(--text-secondary);font-size:12px;line-height:1.5}.rules-head code{font-size:11px}.rule-row{display:grid;grid-template-columns:1fr auto 1fr auto;gap:8px;align-items:center}.rule-row input{min-width:0}.section-hint{margin:0 0 10px}.resource-option{display:flex;align-items:center;gap:10px;padding:9px 2px;border-top:1px solid var(--border);font-size:13px;cursor:pointer}.resource-option span{display:grid;gap:2px;min-width:0}.resource-option b{font-size:13px}.resource-option small{color:var(--text-muted);font:11px ui-monospace,monospace;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.files-head{display:flex;justify-content:space-between;gap:16px;align-items:start}.quick{display:flex;gap:12px}.file-table{margin-top:16px;border-top:1px solid var(--border)}.file-table .virtual-row .import-file{height:100%;border-bottom:1px solid var(--border)}.import-file{min-height:45px;display:grid;grid-template-columns:22px minmax(0,1fr) 78px 56px;align-items:center;gap:8px;border-bottom:1px solid var(--border);font-size:13px;cursor:pointer}.import-file.cached .filename{color:var(--text-secondary)}.filename{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.import-file small{color:var(--text-muted);text-align:right}.import-file em{font-style:normal;color:var(--success);font-size:11px;text-align:right}.files footer{display:flex;justify-content:space-between;align-items:center;padding-top:18px;color:var(--text-secondary);font-size:13px}@media(max-width:600px){.entry-bottom{display:grid}.entry-bottom .btn{width:100%}.summary{align-items:start;gap:14px}.files-head{display:grid}.import-file{grid-template-columns:20px minmax(0,1fr) 64px}.import-file em{display:none}}
.modal-mask{position:fixed;inset:0;z-index:60;background:rgb(0 0 0 / .6);display:grid;place-items:center;padding:14px}
.modal{width:min(560px,100%);max-height:86vh;overflow-y:auto;background:var(--bg-primary);border:1px solid var(--border);border-radius:10px;padding:20px}
.modal header{display:flex;justify-content:space-between;align-items:start;gap:12px;margin-bottom:12px}
.modal header h2{font-size:19px;margin:0 0 6px}
.modal header p{margin:0;color:var(--text-secondary);font-size:12px;line-height:1.5}
.modal-close{background:transparent;border:0;color:var(--text-muted);font-size:22px;line-height:1;cursor:pointer;padding:2px 6px}
.conflict-message{margin:0 0 12px;font-size:13px;color:var(--text-secondary);line-height:1.6}
.raw-error{margin:0 0 12px;font-size:12px;color:var(--danger, #e5484d);line-height:1.6;word-break:break-all}
.record-list{display:grid;gap:8px;max-height:260px;overflow-y:auto;margin-bottom:10px}
.record-row{display:flex;justify-content:space-between;gap:10px;align-items:center;padding:9px 10px;background:var(--bg-card);border:1px solid var(--border);border-radius:6px;font-size:12px}
.record-row span{display:grid;gap:3px;min-width:0}
.record-row b{font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.record-row small{color:var(--text-muted);font-size:11px}
.record-row em{font-style:normal;color:var(--text-secondary);white-space:nowrap}
.record-tip{margin:0 0 4px;font-size:12px;color:var(--text-muted);line-height:1.6}
.modal footer{display:flex;justify-content:flex-end;gap:10px;padding-top:14px}
</style>
