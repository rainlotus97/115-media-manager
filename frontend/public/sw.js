const CACHE = 'pan115-v3'
const STATIC = ['/', '/index.html', '/manifest.webmanifest', '/icons/icon-192.png', '/icons/icon-512.png', '/icons/apple-touch-icon.png']

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(STATIC)).then(() => self.skipWaiting()))
})

self.addEventListener('activate', (event) => {
  event.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))).then(() => self.clients.claim()))
})

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url)
  if (url.pathname.startsWith('/api/')) return
  if (url.pathname.startsWith('/@vite/') || url.pathname.startsWith('/src/') || url.pathname.startsWith('/node_modules/')) return
  if (event.request.method !== 'GET') return
  event.respondWith((async () => {
    const cached = await caches.match(event.request)
    if (cached) return cached
    try {
      const response = await fetch(event.request)
      if (response.ok && url.origin === self.location.origin) {
        const copy = response.clone()
        caches.open(CACHE).then((cache) => cache.put(event.request, copy))
      }
      return response
    } catch {
      return new Response('', { status: 503, statusText: 'Offline' })
    }
  })())
})
