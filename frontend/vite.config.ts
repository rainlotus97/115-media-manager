import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  plugins: [vue()],
  base: '/',
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  build: {
    outDir: resolve(__dirname, 'dist'),
    emptyOutDir: true,
    // 保持 max-width/min-width 写法，兼容旧版手机浏览器（避免被转成 (width<=767px) 后丢失规则）
    cssMinify: false,
  },
  server: {
    // 监听所有网卡：本机 localhost 和同一 WiFi 下的手机都能访问
    host: '0.0.0.0',
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://localhost:8767',
        changeOrigin: true,
      },
    },
  },
})
