import assert from 'node:assert/strict'
import { createServer } from 'vite'
import { createSeed } from '../src/api/mock/seed.js'
import { allPages, byNewest, heatCells, nightHours } from '../src/utils/dashboard.js'

const vite = await createServer({ server: { middlewareMode: true }, appType: 'custom' })
try {
  const { mockRequest } = await vite.ssrLoadModule('/src/api/mock/server.js')
  const seed = createSeed()
  const token = 'mock-' + seed.sys_user.find((u) => u.username === 'analyst1').user_id
  const get = async (path, params = {}, as = token) => {
    const response = await mockRequest('GET', path + '?' + new URLSearchParams(params), { token: as })
    assert.equal(response.status, 200, response.body.message)
    return response.body.data
  }
  const batches = (await allPages((p) => get('/api/batches', p), { run_status: 2 }))
    .filter((b) => b.judge_object === 1).sort(byNewest)
  assert.ok(batches.length)
  const scores = await allPages((p) => get('/api/region-risk', p), { batch_id: batches[0].batch_id })
  assert.ok(scores.length)
  assert.ok(scores.every((s) => s.batch_id === batches[0].batch_id))
  assert.equal(scores.length, seed.risk_score.filter((s) => s.object_type === 1 && s.batch_id === batches[0].batch_id).length)
  for (const day of [1, 2]) assert.equal(heatCells(scores, day).length, scores.filter((s) => s.day_type === day).length)
  assert.throws(() => heatCells([scores[0], scores[0]], scores[0].day_type), /重复/)
  assert.equal(nightHours.length, 24)
  assert.equal(nightHours.indexOf(0), nightHours.indexOf(23) + 1)

  const dictionary = await get('/api/dicts')
  assert.ok(dictionary.rules.every((r) => Number.isFinite(r.low_threshold) && Number.isFinite(r.high_threshold)))
  assert.equal(dictionary.features.length, seed.feature_def.length)

  const all = await allPages((p) => get('/api/region-risk', p))
  assert.equal(all.length, seed.risk_score.filter((s) => s.object_type === 1).length)
  const paginated = await allPages(async ({ page }) => ({ list: Array.from({ length: page < 3 ? 200 : 51 }, (_, i) => (page - 1) * 200 + i), size: 200, total: 451 }))
  assert.equal(paginated.length, 451)
  assert.equal(new Set(paginated).size, 451)

  const map = await get('/api/risk-map')
  for (const night of map.risk) for (const area of night.areas) {
    const score = seed.risk_score.find((s) => s.score_id === area.score_id)
    assert.ok(score)
    assert.equal(score.area_id, area.area_id)
    assert.equal(score.total_score, area.total_score)
  }
  const areaId = map.risk.at(-1).areas[0].area_id
  const clues = await allPages((p) => get('/api/clues', p), { area_id: areaId })
  assert.ok(clues.every((c) => c.area_id === areaId))

  for (const name of ['admin', 'dataop', 'featop']) {
    const as = 'mock-' + seed.sys_user.find((u) => u.username === name).user_id
    assert.equal((await mockRequest('GET', '/api/risk-map', { token: as })).status, 403)
    assert.equal((await mockRequest('GET', '/api/region-risk', { token: as })).status, 403)
  }
  const teacher = 'mock-' + seed.sys_user.find((u) => u.username === 'teacher').user_id
  assert.equal((await mockRequest('PATCH', `/api/clues/${seed.risk_clue[0].clue_id}/status`, { token: teacher, body: { status: 1 } })).status, 403)
  console.log('PASS: single-batch scope, night hours, rule thresholds, pagination, map links, area filtering, role access')
} finally {
  await vite.close()
}
