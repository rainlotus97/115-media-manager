<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useAuth } from '../composables/useAuth'
import { useCookie } from '../composables/useCookie'
import { useToast } from '../composables/useToast'

const { user } = useAuth()
const { cookieValid, check: checkCookie, save: saveCookie } = useCookie()
const { show: toast } = useToast()

import { api } from '../api'

const cookieInput = ref('')
const savingCookie = ref(false)

// TMDB
const tmdbConfigured = ref(false)
const tmdbKey = ref('')
const savingTmdb = ref(false)

async function loadTmdbConfig() {
  try { const r = await api.getTMDBConfig(); tmdbConfigured.value = r.configured } catch { /**/ }
}

async function handleSaveTmdb() {
  if (!tmdbKey.value.trim()) { toast('请输入 API Key', 'error'); return }
  savingTmdb.value = true
  try {
    const res = await api.setTMDBConfig(tmdbKey.value.trim())
    if (res.ok) { tmdbConfigured.value = true; tmdbKey.value = ''; toast('TMDB API Key 已保存', 'success') }
    else toast('保存失败', 'error')
  } catch { toast('请求失败', 'error') }
  finally { savingTmdb.value = false }
}

// 设置 Tab
const settingsTab = ref<'cookie' | 'tmdb' | 'account'>('cookie')

onMounted(() => {
  checkCookie()
  loadTmdbConfig()
})

async function handleSaveCookie() {
  const val = cookieInput.value.trim()
  if (!val) {
    toast('请粘贴 Cookie', 'error')
    return
  }

  savingCookie.value = true
  const res = await saveCookie(val)
  savingCookie.value = false

  if (res.ok) {
    toast('Cookie 已保存并验证通过', 'success')
    cookieInput.value = ''
  } else {
    toast(res.error || 'Cookie 无效', 'error')
  }
}
</script>

<template>
  <div class="settings-page">
    <h1 class="page-title">设置</h1>

    <!-- Sub Tabs -->
    <div class="settings-tabs">
      <button
        :class="['sub-tab', { active: settingsTab === 'cookie' }]"
        @click="settingsTab = 'cookie'"
      >
        115 网盘
      </button>
      <button
        :class="['sub-tab', { active: settingsTab === 'tmdb' }]"
        @click="settingsTab = 'tmdb'; loadTmdbConfig()"
      >
        TMDB
      </button>
      <button
        :class="['sub-tab', { active: settingsTab === 'account' }]"
        @click="settingsTab = 'account'"
      >
        账号
      </button>
    </div>

    <!-- Cookie Settings -->
    <div v-if="settingsTab === 'cookie'" class="settings-section">
      <div class="setting-card">
        <div class="setting-header">
          <h3>115 Cookie 配置</h3>
          <span
            :class="[
              'status-badge',
              cookieValid === true ? 'valid' : cookieValid === false ? 'invalid' : 'unknown',
            ]"
          >
            {{
              cookieValid === true
                ? '✅ 有效'
                : cookieValid === false
                  ? '❌ 无效'
                  : '⏳ 未检测'
            }}
          </span>
        </div>

        <div class="cookie-hint">
          <p>浏览器打开 115.com → F12 → Application → Cookies → 115.com → 复制全部 Cookie 值</p>
        </div>

        <div class="form-group">
          <textarea
            v-model="cookieInput"
            rows="5"
            placeholder="粘贴 Cookie... uid=xxx; cid=xxx; seid=xxx; kid=xxx;"
            class="cookie-textarea"
          ></textarea>
        </div>

        <button
          class="btn btn-primary"
          :disabled="savingCookie"
          @click="handleSaveCookie"
        >
          <span v-if="savingCookie" class="spinner"></span>
          <span v-else>💾 保存并验证</span>
        </button>
      </div>

      <!-- Mobile Cookie Guide -->
      <div class="setting-card">
        <h3>移动端授权</h3>
        <p class="hint-text">
          手机端复制 Cookie 较不方便。你可以：
        </p>
        <ol class="guide-list">
          <li>在 PC/平板浏览器登录 115.com 后复制 Cookie</li>
          <li>通过剪贴板同步工具（如 iCloud 剪贴板）传到手机</li>
          <li>粘贴到上方输入框保存</li>
        </ol>
        <div class="mobile-note">
          💡 扫码授权功能将在后续版本中研究支持
        </div>
      </div>
    </div>

    <!-- TMDB Settings -->
    <div v-if="settingsTab === 'tmdb'" class="settings-section">
      <div class="setting-card">
        <div class="setting-header">
          <h3>TMDB API 配置</h3>
          <span :class="['status-badge', tmdbConfigured ? 'valid' : 'unknown']">
            {{ tmdbConfigured ? '✅ 已配置' : '⏳ 未配置' }}
          </span>
        </div>
        <p class="hint-text" style="margin-bottom:12px">
          用于获取电影/电视剧/动漫的元数据（海报、简介、集数等）。
          免费注册获取 API Key：<a href="https://www.themoviedb.org/settings/api" target="_blank">themoviedb.org/settings/api</a>
        </p>
        <div class="form-group">
          <input
            v-model="tmdbKey"
            type="text"
            placeholder="粘贴 TMDB API Key (v3 auth)"
          />
        </div>
        <button class="btn btn-primary" :disabled="savingTmdb" @click="handleSaveTmdb">
          <span v-if="savingTmdb" class="spinner"></span>
          <span v-else>💾 保存</span>
        </button>
      </div>
    </div>

    <!-- Account Settings -->
    <div v-if="settingsTab === 'account'" class="settings-section">
      <div class="setting-card">
        <div class="account-info">
          <div class="account-avatar">👤</div>
          <div class="account-detail">
            <div class="account-name">{{ user?.username }}</div>
            <div class="account-id">ID: {{ user?.id }}</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.settings-page {
  max-width: 640px;
}

.page-title {
  font-size: 24px;
  font-weight: 700;
  margin-bottom: 24px;
}

.settings-tabs {
  display: flex;
  gap: 4px;
  margin-bottom: 24px;
  background: var(--bg-card);
  border-radius: var(--radius);
  padding: 4px;
}

.sub-tab {
  flex: 1;
  padding: 10px 16px;
  text-align: center;
  border: none;
  background: transparent;
  border-radius: var(--radius-sm);
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all var(--transition);
}

.sub-tab.active {
  background: var(--accent);
  color: #fff;
}

.sub-tab:not(.active):hover {
  background: var(--bg-card-hover);
}

.settings-section {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.setting-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 24px;
}

.setting-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.setting-card h3 {
  font-size: 16px;
  font-weight: 600;
}

.status-badge {
  font-size: 12px;
  font-weight: 600;
  padding: 4px 10px;
  border-radius: 20px;
}

.status-badge.valid {
  background: rgba(52, 199, 89, 0.15);
  color: var(--success);
}

.status-badge.invalid {
  background: rgba(255, 69, 58, 0.15);
  color: var(--danger);
}

.status-badge.unknown {
  background: rgba(142, 142, 154, 0.15);
  color: var(--text-muted);
}

.cookie-hint {
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 14px;
  line-height: 1.5;
}

.cookie-textarea {
  font-family: 'SF Mono', 'Fira Code', monospace;
  font-size: 12px !important;
  line-height: 1.4;
}

.form-group {
  margin-bottom: 14px;
}

.hint-text {
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 10px;
}

.guide-list {
  font-size: 13px;
  color: var(--text-secondary);
  padding-left: 18px;
  line-height: 2;
}

.mobile-note {
  margin-top: 12px;
  padding: 10px 14px;
  background: rgba(91, 127, 255, 0.1);
  border-radius: var(--radius-sm);
  font-size: 12px;
  color: var(--accent);
}

.account-info {
  display: flex;
  align-items: center;
  gap: 16px;
}

.account-avatar {
  font-size: 48px;
}

.account-name {
  font-size: 18px;
  font-weight: 700;
}

.account-id {
  font-size: 13px;
  color: var(--text-muted);
  margin-top: 2px;
}
</style>
