import { ref, computed } from 'vue'
import { api } from '../api'
import type { UserInfo } from '../types'

const user = ref<UserInfo | null>(null)
const token = ref<string | null>(localStorage.getItem('token'))

const isLoggedIn = computed(() => !!token.value && !!user.value)

export function useAuth() {
  async function login(username: string, password: string): Promise<string | undefined> {
    const res = await api.login(username, password)
    if (res.ok && res.token && res.user) {
      token.value = res.token
      user.value = res.user
      localStorage.setItem('token', res.token)
      return undefined
    }
    return res.error || '登录失败'
  }

  async function register(username: string, password: string): Promise<string | undefined> {
    const res = await api.register(username, password)
    if (res.ok && res.token && res.user) {
      token.value = res.token
      user.value = res.user
      localStorage.setItem('token', res.token)
      return undefined
    }
    return res.error || '注册失败'
  }

  async function restoreSession(): Promise<boolean> {
    const savedToken = localStorage.getItem('token')
    if (!savedToken) return false
    token.value = savedToken
    try {
      const res = await api.getSession()
      if (res.ok && res.user) {
        user.value = res.user
        return true
      }
    } catch {
      // session expired
    }
    token.value = null
    user.value = null
    localStorage.removeItem('token')
    return false
  }

  function logout() {
    token.value = null
    user.value = null
    localStorage.removeItem('token')
  }

  return { user, token, isLoggedIn, login, register, restoreSession, logout }
}
