<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { api, getGatewayUrl, setGatewayUrl, isNativePlatform } from '../api'
import { useToast } from '../composables/useToast'

const { show: toast } = useToast()
const isNative = isNativePlatform
const connected = ref<boolean | null>(null)
const sessionCached = ref(false)
const qrLoading = ref(false)
const qrUrl = ref('')
const qrUid = ref('')
const qrStatus = ref('')
const qrExpiresAt = ref(0)
const gateway = ref(getGatewayUrl())
const tmdbKey = ref('')
const tmdbConfigured = ref(false)
const tmdbSaving = ref(false)
const QR_STORAGE_KEY = 'pan115-active-qr'
let qrTimer: number | undefined

const hasActiveQr = computed(() => Boolean(qrUid.value && qrUrl.value && Date.now() < qrExpiresAt.value))

function saveQrState() {
  sessionStorage.setItem(QR_STORAGE_KEY, JSON.stringify({
    uid: qrUid.value,
    url: qrUrl.value,
    expiresAt: qrExpiresAt.value,
  }))
}
function restoreQrState() {
  try {
    const saved = JSON.parse(sessionStorage.getItem(QR_STORAGE_KEY) || 'null')
    if (saved?.uid && saved?.url && saved.expiresAt > Date.now()) {
      qrUid.value = saved.uid
      qrUrl.value = saved.url
      qrExpiresAt.value = saved.expiresAt
      return true
    }
  } catch { /* ignore */ }
  sessionStorage.removeItem(QR_STORAGE_KEY)
  return false
}
function clearQrState() {
  sessionStorage.removeItem(QR_STORAGE_KEY)
  qrUid.value = ''
  qrUrl.value = ''
  qrExpiresAt.value = 0
}

async function refresh() {
  try {
    const session = await api.getSession()
    connected.value = session.ok
    sessionCached.value = Boolean(session.cached)
  } catch { connected.value = false; sessionCached.value = false }
}
async function saveGateway() {
  setGatewayUrl(gateway.value)
  await refresh()
  toast(gateway.value.trim() ? '网关地址已保存' : '已使用当前网页地址', 'success')
}
async function refreshTmdb() {
  try {
    const config = await api.getTmdbConfig()
    tmdbConfigured.value = config.configured
  } catch { tmdbConfigured.value = false }
}
async function saveTmdb() {
  if (!tmdbKey.value.trim()) { toast('请输入 TMDB API Key', 'error'); return }
  tmdbSaving.value = true
  try {
    await api.setTmdbConfig(tmdbKey.value.trim())
    tmdbKey.value = ''
    tmdbConfigured.value = true
    toast('TMDB API Key 已保存', 'success')
  } catch (error: any) {
    toast(error.message || '保存失败', 'error')
  } finally { tmdbSaving.value = false }
}
async function logout() {
  if (!confirm('退出 115 授权？本地资源索引不会删除。')) return
  try { await api.logout(); connected.value = false; clearQrState(); toast('已退出 115 授权', 'success') } catch { toast('退出失败', 'error') }
}

function stopPolling() {
  window.clearInterval(qrTimer)
  qrTimer = undefined
}
function startPolling() {
  stopPolling()
  qrTimer = window.setInterval(async () => {
    if (!qrUid.value) return
    try {
      const state = await api.getQrLoginStatus(qrUid.value)
      if (state.status === 'authorized') {
        stopPolling(); clearQrState(); qrLoading.value = false
        await refresh(); toast('115 扫码授权成功', 'success')
      } else if (state.status === 'scanned') {
        qrStatus.value = '已扫码，请在 115 App 中确认'
      } else if (state.status === 'confirmed') {
        qrStatus.value = '已确认，正在获取授权'
      } else if (state.status === 'expired' || state.status === 'canceled') {
        stopPolling(); clearQrState(); qrLoading.value = false; qrStatus.value = '二维码已失效，请重新生成'
      } else if (state.error) {
        qrStatus.value = state.error
      }
    } catch { /* transient polling failure */ }
  }, 1800)
}
async function startQrLogin(forceNew = false) {
  if (forceNew) clearQrState()
  if (!qrUrl.value && !restoreQrState()) {
    qrLoading.value = true
    qrStatus.value = ''
    try {
      const result = await api.createQrLogin()
      if (!result.ok || !result.uid || !result.qr_url) throw new Error(result.error || '二维码生成失败')
      qrUid.value = result.uid
      qrUrl.value = result.qr_url
      qrExpiresAt.value = Date.now() + (result.expires_in || 300) * 1000
      saveQrState()
    } catch (error: any) {
      qrLoading.value = false
      toast(error.message || '二维码生成失败', 'error')
      return
    }
  }
  qrLoading.value = false
  qrStatus.value = '请使用 115 App 扫描屏幕上的二维码并确认'
  startPolling()
}
function hideQr() {
  // 只收起界面，不销毁服务端会话：5 分钟内重新打开仍可继续等待扫码。
  stopPolling()
  qrUrl.value = ''
  qrStatus.value = '二维码已收起；扫码结果在有效期内仍然有效，可重新显示继续等待。'
}

onMounted(() => { refresh(); refreshTmdb() })
onUnmounted(stopPolling)
</script>
<template>
  <section class="settings-page"><header><p class="eyebrow">SETTINGS</p><h1>设置</h1><p>115 采用扫码授权，不需要手动复制 Cookie。</p></header>
    <div v-if="!isNative" class="gateway-card"><h2>服务网关</h2><p>手机、平板与电脑使用同一页面；若部署在服务器，请填写 HTTPS 地址，例如 <code>https://pan.example.com</code>。</p><div><input v-model="gateway" type="url" placeholder="https://pan.example.com" /><button class="btn btn-ghost" @click="saveGateway">保存地址</button></div></div>
    <div class="status-card"><span class="status-dot" :class="{ on: connected }" /><div><b>{{ connected === null ? '正在检查授权' : connected ? '115 已连接' : '需要重新授权' }}</b><p>{{ connected ? (sessionCached ? '已复用本地授权缓存，尚未过期。' : '授权已验证，资源导入和云下载可以正常使用。') : '请登录 115 以继续使用资源管理能力。' }}</p></div><button v-if="connected" class="btn btn-ghost" @click="logout">退出授权</button></div>
    <div v-if="!connected" class="login-card"><h2>扫码授权登录</h2><p>用 115 App 扫描屏幕上的二维码并确认。取消只会收起二维码，不会影响扫码结果。</p><div v-if="qrUrl" class="qr-login"><img :src="qrUrl" alt="115 登录二维码" /><strong>{{ qrStatus }}</strong><div class="qr-actions"><button class="btn btn-ghost" @click="hideQr">收起二维码</button><button class="btn btn-primary" @click="startQrLogin(true)">重新生成</button></div></div><div v-else class="qr-start"><button class="btn btn-primary" :disabled="qrLoading" @click="startQrLogin()"><span v-if="qrLoading" class="spinner" /><span v-else>{{ hasActiveQr ? '重新显示二维码' : '生成登录二维码' }}</span></button><p v-if="qrStatus">{{ qrStatus }}</p></div></div>
    <div class="gateway-card"><h2>TMDB</h2><p>{{ tmdbConfigured ? '已配置 TMDB API Key，可以搜索并对比剧集总集数。' : '未配置 TMDB API Key，搜索剧集和集数对比不可用。' }}</p><div><input v-model="tmdbKey" type="password" placeholder="TMDB API Key（v3 auth）" autocomplete="off" /><button class="btn btn-ghost" :disabled="tmdbSaving" @click="saveTmdb"><span v-if="tmdbSaving" class="spinner" /><span v-else>保存 Key</span></button></div></div>
    <div class="privacy"><h2>本地数据</h2><p>资源名称、文件索引和 115 目录映射持久化在当前设备。移除资源只会移除索引，不会删除 115 云端文件。</p></div>
  </section>
</template>
<style scoped>
.settings-page{max-width:680px;margin:0 auto}.eyebrow{font-size:11px;font-weight:700;color:var(--accent);margin:0 0 7px}h1{font-size:28px;margin:0 0 8px}header>p:last-child{margin:0;color:var(--text-secondary);font-size:14px}.gateway-card,.status-card,.login-card,.privacy{margin-top:24px;padding:20px;background:var(--bg-card);border:1px solid var(--border);border-radius:7px}.gateway-card h2{font-size:16px;margin:0}.gateway-card p{color:var(--text-secondary);font-size:13px;line-height:1.5}.gateway-card div{display:flex;gap:10px}.gateway-card input{flex:1}.status-card{display:flex;align-items:center;gap:12px}.status-card div{flex:1}.status-card b{font-size:14px}.status-card p,.login-card>p,.privacy p,.qr-start p{font-size:13px;color:var(--text-secondary);margin:5px 0 0}.status-dot{width:9px;height:9px;border-radius:50%;background:var(--danger)}.status-dot.on{background:var(--success)}.login-card{display:grid;gap:15px}.login-card h2,.privacy h2{font-size:16px;margin:0}.login-card>p{margin-top:-8px}.login-card .btn{justify-self:start}.privacy{margin-top:12px}.privacy p{line-height:1.6}.qr-start{display:grid;gap:10px;justify-items:start}.qr-start .btn{min-width:150px}.qr-login{display:grid;justify-items:center;gap:10px}.qr-login img{width:220px;height:220px;image-rendering:auto;background:#fff;padding:8px;border-radius:6px}.qr-login strong{font-size:13px;color:var(--text-secondary)}.qr-actions{display:flex;gap:10px}.qr-actions .btn{min-width:112px}@media(max-width:520px){.gateway-card div{display:grid}.gateway-card .btn{width:100%}.status-card{align-items:start;flex-wrap:wrap}.status-card .btn{width:100%;margin-top:4px}.login-card .btn{width:100%}.qr-start .btn,.qr-actions{width:100%}.qr-actions .btn{width:100%}}
</style>
