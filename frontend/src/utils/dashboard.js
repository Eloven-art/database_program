// 完整读取分页数据，避免概览只展示第一页而误当作全部。
export async function allPages(fetcher, params = {}) {
  const first = await fetcher({ ...params, page: 1, size: 200 })
  const rows = [...first.list]
  for (let page = 2; rows.length < first.total; page++) {
    const next = await fetcher({ ...params, page, size: first.size })
    if (!next.list.length) throw new Error('数据分页不完整，请刷新重试')
    rows.push(...next.list)
  }
  return rows
}

export const nightHours = Array.from({ length: 24 }, (_, i) => (i + 6) % 24)
export const byNewest = (a, b) => b.created_at.localeCompare(a.created_at) || b.batch_id.localeCompare(a.batch_id)
export const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c])

export function heatCells(rows, dayType) {
  const cells = new Map()
  for (const row of rows.filter((r) => r.day_type === dayType)) {
    const key = `${row.area_id}:${row.hour_slot}`
    if (cells.has(key)) throw new Error('当前批次存在重复区域时段评分，请检查数据')
    cells.set(key, row)
  }
  return [...cells.values()]
}
