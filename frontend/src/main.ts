import { createApp } from 'vue'
import './assets/main.css'
import App from './App.vue'

createApp(App).mount('#app')

if ('serviceWorker' in navigator) {
  if (import.meta.env.DEV) {
    // 开发模式彻底停用 Service Worker：清掉可能残留的旧注册和缓存，
    // 避免它缓存 /@vite/client 等模块导致 HMR WebSocket 一直连不上。
    navigator.serviceWorker.getRegistrations().then((regs) => {
      regs.forEach((reg) => reg.unregister())
    })
    if (window.caches) {
      window.caches.keys().then((keys) => keys.forEach((key) => window.caches.delete(key)))
    }
  } else {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('/sw.js').catch(() => { /* 忽略 PWA 注册失败 */ })
    })
  }
}
