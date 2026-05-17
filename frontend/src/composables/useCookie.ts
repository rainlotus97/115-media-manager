import { ref } from 'vue'
import { api } from '../api'

const cookieValid = ref<boolean | null>(null)

export function useCookie() {
  async function check() {
    try {
      const res = await api.checkCookie()
      cookieValid.value = res.ok
    } catch {
      cookieValid.value = false
    }
  }

  async function getStatus(): Promise<boolean> {
    try {
      const res = await api.getCookieStatus()
      return res.has_cookie ?? false
    } catch {
      return false
    }
  }

  async function save(cookie: string): Promise<{ ok: boolean; error?: string }> {
    try {
      const res = await api.saveCookie(cookie)
      if (res.ok) cookieValid.value = true
      else cookieValid.value = false
      return { ok: res.ok, error: res.error }
    } catch {
      cookieValid.value = false
      return { ok: false, error: '请求失败' }
    }
  }

  return { cookieValid, check, getStatus, save }
}
