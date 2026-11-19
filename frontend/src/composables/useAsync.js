import { ref, shallowRef } from 'vue'

// 统一管理"加载中 / 空数据 / 接口报错"三种状态（《前端交接文档》第十三节验收项）
export function useAsync(fn, { immediate = true } = {}) {
  const data = shallowRef(null)
  const loading = ref(false)
  const error = ref(null)
  let requestId = 0

  async function run(...args) {
    const id = ++requestId
    loading.value = true
    error.value = null
    try {
      const result = await fn(...args)
      if (id === requestId) data.value = result
    } catch (e) {
      if (id === requestId) error.value = e
    } finally {
      if (id === requestId) loading.value = false
    }
    return data.value
  }

  if (immediate) run()
  return { data, loading, error, run }
}
