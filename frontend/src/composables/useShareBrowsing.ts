import { reactive, computed } from 'vue'
import { api } from '../api'
import type { FileItem, Breadcrumb } from '../types'

interface BrowseState {
  url: string
  password: string
  shareCode: string
  title: string
  userName: string
  fileCount: number
  sizeStr: string
  isExpired: boolean
  files: FileItem[]
  fileIdMap: Record<string, string>
  browseCid: string
  breadcrumbs: Breadcrumb[]
  selectedFileIds: Set<string>
  loading: boolean
  hasData: boolean
  targetPath: string
}

export function useShareBrowsing() {
  const state = reactive<BrowseState>({
    url: '',
    password: '',
    shareCode: '',
    title: '',
    userName: '',
    fileCount: 0,
    sizeStr: '',
    isExpired: false,
    files: [],
    fileIdMap: {},
    browseCid: '0',
    breadcrumbs: [{ name: '全部文件', cid: '0' }],
    selectedFileIds: new Set(),
    loading: false,
    hasData: false,
    targetPath: '',
  })

  const selectedCount = computed(() => state.selectedFileIds.size)
  const totalCount = computed(() => state.files.length)
  const allSelected = computed(
    () => totalCount.value > 0 && selectedCount.value === totalCount.value
  )

  function getFid(file: FileItem): string {
    for (const [k, v] of Object.entries(state.fileIdMap)) {
      if (v === file.name) return k
    }
    return ''
  }

  function isSelected(file: FileItem): boolean {
    const fid = getFid(file)
    return fid ? state.selectedFileIds.has(fid) : false
  }

  async function fetchInfo(url: string, password: string, cid?: string) {
    state.loading = true
    const res = await api.getShareInfo({ url, password, cid })
    state.loading = false

    if (!res.ok) throw new Error(res.error || res.hint || '获取分享信息失败')

    state.url = url
    state.password = password
    state.shareCode = res.share_code || ''
    state.title = res.title || ''
    state.userName = res.user_name || ''
    state.fileCount = res.file_count || 0
    state.sizeStr = res.size_str || ''
    state.isExpired = res.is_expired || false
    state.files = res.files || []
    state.fileIdMap = res.file_id_map || {}
    state.browseCid = res.browse_cid || '0'
    state.hasData = true

    // default select all
    state.selectedFileIds = new Set(Object.keys(res.file_id_map || {}))

    // reset breadcrumbs on new top-level fetch
    if (!cid || cid === '0') {
      state.breadcrumbs = [{ name: '全部文件', cid: '0' }]
    }

    // auto-fill target path
    if (!state.targetPath) {
      const clean = (state.title || '').split('.').filter(Boolean)[0] || state.title
      state.targetPath = '资源库/115转存/' + clean
    }
  }

  function toggleSelectAll(checked: boolean) {
    if (checked) {
      state.selectedFileIds = new Set(Object.keys(state.fileIdMap))
    } else {
      state.selectedFileIds = new Set()
    }
  }

  function toggleFile(fid: string) {
    const next = new Set(state.selectedFileIds)
    if (next.has(fid)) next.delete(fid)
    else next.add(fid)
    state.selectedFileIds = next
  }

  async function browseTo(cid: string) {
    state.breadcrumbs = state.breadcrumbs.slice(
      0,
      state.breadcrumbs.findIndex((b) => b.cid === cid) + 1 || 1
    )
    await fetchInfo(state.url, state.password, cid)
  }

  async function browseToFolder(fid: string, name: string) {
    state.breadcrumbs.push({ name, cid: fid })
    await fetchInfo(state.url, state.password, fid)
  }

  async function browseUp() {
    if (state.breadcrumbs.length <= 1) return
    const prev = state.breadcrumbs[state.breadcrumbs.length - 2]
    state.breadcrumbs = state.breadcrumbs.slice(0, -1)
    await fetchInfo(state.url, state.password, prev.cid)
  }

  function reset() {
    state.url = ''
    state.password = ''
    state.hasData = false
    state.files = []
    state.fileIdMap = {}
    state.browseCid = '0'
    state.breadcrumbs = [{ name: '全部文件', cid: '0' }]
    state.selectedFileIds = new Set()
  }

  function getSelectedFileIds(): string {
    return Array.from(state.selectedFileIds).join(',')
  }

  return {
    state,
    selectedCount,
    totalCount,
    allSelected,
    getFid,
    isSelected,
    fetchInfo,
    toggleSelectAll,
    toggleFile,
    browseTo,
    browseToFolder,
    browseUp,
    reset,
    getSelectedFileIds,
  }
}
