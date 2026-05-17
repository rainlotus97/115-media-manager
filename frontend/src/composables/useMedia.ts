import { ref } from 'vue'
import { api } from '../api'
import type { WatchlistItem, TMDBSearchItem, TMDBDetailResponse } from '../types'

const items = ref<WatchlistItem[]>([])
const selectedItem = ref<WatchlistItem | null>(null)
const loading = ref(false)

export function useMedia() {
  async function fetchList(type?: string, region?: string, status?: string) {
    loading.value = true
    try {
      const res = await api.getWatchlist(type, region, status)
      if (res.ok) items.value = res.items
    } catch {
      items.value = []
    } finally {
      loading.value = false
    }
  }

  async function fetchDetail(id: number) {
    const res = await api.getWatchlistDetail(id)
    if (res.ok && res.item) {
      selectedItem.value = res.item
      return res.item
    }
    return null
  }

  async function add(mediaType: string, tmdbResult: TMDBSearchItem | TMDBDetailResponse, path115: string) {
    const res = await api.addWatchlist({
      tmdb_id: tmdbResult.tmdb_id,
      title: tmdbResult.title || '',
      original_title: tmdbResult.original_title,
      media_type: mediaType,
      region: ('region' in tmdbResult ? tmdbResult.region : '') || '',
      genres: 'genres' in tmdbResult ? tmdbResult.genres : [],
      poster_url: tmdbResult.poster_url || '',
      backdrop_url: tmdbResult.backdrop_url || '',
      overview: (tmdbResult as any).overview || '',
      total_episodes: 'total_episodes' in tmdbResult ? (tmdbResult.total_episodes || 0) : 0,
      path_115: path115,
    })
    return res
  }

  async function remove(id: number) {
    const res = await api.deleteWatchlist(id)
    if (res.ok) {
      items.value = items.value.filter((i) => i.id !== id)
    }
    return res
  }

  async function syncItem(id: number) {
    const res = await api.syncWatchlist(id)
    return res.ok
  }

  return { items, selectedItem, loading, fetchList, fetchDetail, add, remove, syncItem }
}
