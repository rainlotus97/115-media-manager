import type { Resource, ResourceFile } from '../types'

const DB_NAME = '115-resource-manager'
const STORE = 'snapshots'

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, 1)
    request.onupgradeneeded = () => request.result.createObjectStore(STORE)
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error)
  })
}

export function useResourceCache() {
  async function get<T>(key: string): Promise<T | null> {
    try {
      const db = await openDb()
      return await new Promise(resolve => {
        const request = db.transaction(STORE).objectStore(STORE).get(key)
        request.onsuccess = () => resolve(request.result?.value ?? request.result ?? null)
        request.onerror = () => resolve(null)
      })
    } catch { return null }
  }
  async function set(key: string, value: unknown) {
    try {
      const db = await openDb()
      db.transaction(STORE, 'readwrite').objectStore(STORE).put({ value }, key)
    } catch { /* Browser private mode can reject persistent storage. */ }
  }
  async function remove(key: string) {
    try {
      const db = await openDb()
      db.transaction(STORE, 'readwrite').objectStore(STORE).delete(key)
    } catch { /* ignore */ }
  }
  async function read(): Promise<Resource[] | null> {
    return get<{ items: Resource[] }>('resources').then(r => r?.items ?? null)
  }
  async function write(items: Resource[]) {
    await set('resources', { items, cachedAt: Date.now() })
  }
  async function readFiles(resourceId: number): Promise<ResourceFile[] | null> {
    return get<ResourceFile[]>(`files-${resourceId}`)
  }
  async function writeFiles(resourceId: number, files: ResourceFile[]) {
    await set(`files-${resourceId}`, files)
  }
  async function removeFiles(resourceId: number) {
    await remove(`files-${resourceId}`)
  }
  async function readPoster(resourceId: number): Promise<Blob | null> {
    return get<Blob>(`poster-${resourceId}`)
  }
  async function writePoster(resourceId: number, blob: Blob) {
    await set(`poster-${resourceId}`, blob)
  }
  async function removePoster(resourceId: number) {
    await remove(`poster-${resourceId}`)
  }
  async function nextId(): Promise<number> {
    const current = await get<number>('nextId')
    const next = (current ?? 1000) + 1
    await set('nextId', next)
    return next
  }
  return { read, write, readFiles, writeFiles, removeFiles, readPoster, writePoster, removePoster, nextId }
}
