<script setup lang="ts">
import { ref } from 'vue'
import { useAuth } from '../composables/useAuth'
import { useToast } from '../composables/useToast'

const { login, register } = useAuth()
const { show: toast } = useToast()

const isRegister = ref(false)
const username = ref('')
const password = ref('')
const loading = ref(false)

async function handleSubmit() {
  if (!username.value.trim() || !password.value.trim()) {
    toast('请填写用户名和密码', 'error')
    return
  }

  loading.value = true
  const err = isRegister.value
    ? await register(username.value.trim(), password.value)
    : await login(username.value.trim(), password.value)
  loading.value = false

  if (err) toast(err, 'error')
}
</script>

<template>
  <div class="login-page">
    <div class="login-bg">
      <div class="gradient-orb orb-1"></div>
      <div class="gradient-orb orb-2"></div>
    </div>

    <div class="login-card">
      <div class="login-header">
        <div class="login-icon">📁</div>
        <h1>115 媒体管家</h1>
        <p>追更管理 · 智能同步 · 一键转存</p>
      </div>

      <form @submit.prevent="handleSubmit" class="login-form">
        <div class="form-group">
          <label>用户名</label>
          <input
            v-model="username"
            type="text"
            placeholder="输入用户名"
            autocomplete="username"
          />
        </div>

        <div class="form-group">
          <label>密码</label>
          <input
            v-model="password"
            type="password"
            placeholder="输入密码"
            autocomplete="current-password"
          />
        </div>

        <button class="btn btn-primary btn-block" :disabled="loading" type="submit">
          <span v-if="loading" class="spinner"></span>
          <span v-else>{{ isRegister ? '注册' : '登录' }}</span>
        </button>
      </form>

      <div class="login-footer">
        <button class="btn btn-ghost btn-sm" @click="isRegister = !isRegister">
          {{ isRegister ? '已有账号？去登录' : '没有账号？去注册' }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  overflow: hidden;
  background: var(--bg-primary);
}

.login-bg {
  position: absolute;
  inset: 0;
  overflow: hidden;
}

.gradient-orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(80px);
  opacity: 0.15;
}

.orb-1 {
  width: 500px;
  height: 500px;
  background: var(--accent);
  top: -150px;
  right: -100px;
}

.orb-2 {
  width: 400px;
  height: 400px;
  background: #8b5cf6;
  bottom: -100px;
  left: -80px;
}

.login-card {
  position: relative;
  z-index: 1;
  width: 380px;
  max-width: calc(100vw - 32px);
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-xl);
  padding: 40px 32px;
  box-shadow: 0 24px 80px rgba(0, 0, 0, 0.5);
}

.login-header {
  text-align: center;
  margin-bottom: 32px;
}

.login-icon {
  font-size: 48px;
  margin-bottom: 12px;
}

.login-header h1 {
  font-size: 22px;
  font-weight: 700;
  margin-bottom: 6px;
}

.login-header p {
  font-size: 13px;
  color: var(--text-secondary);
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.login-footer {
  margin-top: 20px;
  text-align: center;
}
</style>
