<template>
  <div class="page">
    <div class="page-head">
      <div><h2>首页概览</h2><p class="sub">以案找线：历史案件 → 风险特征 → 扫描日常数据 → 区域时段风险 → 待核查线索 → 核查结论回流</p></div>
        <div v-if="auth.canBlock('overview.risk') && summary.data.value" class="heading-range">
          <label for="overview-batch">热力图研判批次</label>
          <el-select id="overview-batch" v-model="batchId" aria-label="热力图研判批次" filterable placeholder="暂无成功的区域研判批次" @change="loadRisk">
            <el-option v-for="b in summary.data.value.batches" :key="b.batch_id" :label="b.batch_id" :value="b.batch_id" />
          </el-select>

        </div>
      <el-button :loading="summary.loading.value" @click="refresh">刷新概览</el-button>
    </div>
    <AsyncState :loading="summary.loading.value" :error="summary.error.value" :data="summary.data.value" @retry="refresh">
      <template v-if="summary.data.value">
        <div class="scope-bar"><span>业务指标：全部批次累计</span><span>最近刷新 {{ updatedAt }}</span><span v-if="batch">图表数据窗 {{ batch.data_start }} 至 {{ batch.data_end }}（不含止时）</span></div>
        <div v-if="auth.canBlock('overview.risk') || auth.canBlock('overview.clues')" class="hero-workspace">
          <el-card v-if="auth.canBlock('overview.risk')" shadow="never">
            <template #header><div class="card-title">区域 × 时段风险热力 <router-link :to="{name:'risk-map'}">查看风险地图 →</router-link></div></template>
            <AsyncState :loading="risk.loading.value" :error="risk.error.value" :data="risk.data.value" empty-text="当前批次暂无区域时段评分" @retry="loadRisk"><div class="chart-mode" role="group" aria-label="风险图展示方式"><el-tooltip v-for="mode in [{value:'heat',label:'时段热力',icon:'Grid'},{value:'map',label:'区域分布',icon:'MapLocation'}]" :key="mode.value" :content="mode.label"><button class="view-tab" :class="{active:chartMode===mode.value}" :aria-label="mode.label" :aria-pressed="chartMode===mode.value" @click="chartMode=mode.value"><el-icon><component :is="mode.icon" /></el-icon><span v-if="chartMode===mode.value">{{ mode.label }}</span></button></el-tooltip></div><RiskHeatmap v-if="chartMode==='heat'" :rows="risk.data.value || []" :rule="rule" /><BatchRiskMap v-else :rows="risk.data.value || []" /></AsyncState>
          </el-card>
        <div v-if="auth.canBlock('overview.clues')" class="stat-grid work-stats">
          <button class="stat action-stat" @click="goClues(0)"><span class="label">待核查</span><span class="value warn">{{ summary.data.value.ov.clue_open }}</span><span class="foot">进入待办列表 →</span></button>
          <button class="stat action-stat" @click="goClues(1)"><span class="label">核查中</span><span class="value">{{ summary.data.value.ov.clue_checking }}</span><span class="foot">继续核查 →</span></button>
          <button class="stat action-stat" @click="router.push({name:'risk',query:{risk_level:3}})"><span class="label">高风险区域时段</span><span class="value high">{{ summary.data.value.regionalHigh }}</span><span class="foot">查看全部批次高风险区域评分 →</span></button>
          <div class="stat"><div class="label">已关闭线索</div><div class="value">{{ summary.data.value.ov.clue_confirmed + summary.data.value.ov.clue_excluded }}</div><div class="foot">已确认 {{ summary.data.value.ov.clue_confirmed }} · 已排除 {{ summary.data.value.ov.clue_excluded }} · 总计 {{ summary.data.value.ov.clue_total }}</div></div>
        </div>
        </div>
          <el-card v-if="auth.canBlock('overview.clues')" shadow="never">
            <template #header><div class="card-title">优先处理 <router-link :to="{name:'clues',query:{status:0}}">全部待核查 →</router-link></div><p class="muted card-sub">待核查、核查中的线索，按风险等级和分数优先排列</p></template>
            <el-empty v-if="!summary.data.value.pending.length" description="暂无待处理线索" />
            <div v-else class="todo-list"><router-link v-for="c in summary.data.value.pending" :key="c.clue_id" class="todo-row" :to="{name:'clue-detail',params:{clueId:c.clue_id}}"><div class="todo-title">{{ c.object_type === 2 ? `个人 ${c.object_id}` : `${c.area_name} · ${pad2(c.hour_slot)} 时` }}<b class="num">{{ fixed(c.total_score) }} 分</b></div><div class="todo-meta"><LevelTag :level="c.risk_level" /><StatusTag type="clue_status" :value="c.clue_status" /><span>{{ c.assignee_name || '未分配' }}</span></div><span class="mono muted">{{ c.clue_id }}</span></router-link></div>
          </el-card>
        <div class="overview-support">
          <el-card v-if="auth.canBlock('overview.eval')" shadow="never"><template #header><div class="card-title">评估摘要 <router-link :to="{name:'eval'}">评估报告 →</router-link></div></template><div class="eval-summary"><span>召回率 <b>{{ percent(summary.data.value.ov.eval.recall) }}</b></span><span>精确率 <b>{{ percent(summary.data.value.ov.eval.precision) }}</b></span><span>误报率 <b>{{ percent(summary.data.value.ov.eval.fpr) }}</b></span></div><p class="muted">模拟数据 · 全部批次评估</p></el-card>
          <el-card shadow="never"><template #header><div class="card-title">最近研判批次</div></template><p class="mono">{{ summary.data.value.ov.latest_batch?.batch_id || '—' }}</p><StatusTag v-if="summary.data.value.ov.latest_batch" type="run_status" :value="summary.data.value.ov.latest_batch.run_status" /><p v-if="auth.canPage('ops')"><router-link :to="{name:'ops'}">版本与批次 →</router-link></p></el-card>
        </div>
        <el-card v-if="!auth.canBlock('overview.clues')" shadow="never"><template #header><div class="card-title">你的工作入口</div></template><div class="entries"><el-button v-for="e in entries" :key="e.name" @click="router.push({name:e.name})">{{ e.title }}</el-button><span v-if="!entries.length" class="muted">数据管理员的信息库明细与导入质量报告页面不在本期 12 个页面内；可在页脚查看数据健康检查。</span></div></el-card>
      </template>
    </AsyncState>
  </div>
</template>
<script setup>
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '@/api'
import { useAuthStore } from '@/stores/auth'
import { useAsync } from '@/composables/useAsync'
import { useDicts } from '@/composables/useDicts'
import { pad2, fixed, percent, toDateTime } from '@/utils/format'
import { allPages, byNewest } from '@/utils/dashboard'
import AsyncState from '@/components/AsyncState.vue'
import BatchRiskMap from '@/components/BatchRiskMap.vue'
import RiskHeatmap from '@/components/RiskHeatmap.vue'
import LevelTag from '@/components/LevelTag.vue'
import StatusTag from '@/components/StatusTag.vue'
const auth = useAuthStore(), router = useRouter(), dicts = useDicts()
const batchId = ref(''), updatedAt = ref(''), chartMode = ref('heat')
const risk = useAsync(async () => batchId.value ? allPages(api.regionRisk, {batch_id:batchId.value}) : [], {immediate:false})
const summary = useAsync(async () => {
  const [ov, batches, pending, highRisk] = await Promise.all([
    api.overview(),
    auth.canBlock('overview.risk') ? allPages(api.batches,{run_status:2}) : [],
    auth.canBlock('overview.clues') ? Promise.all([allPages(api.clues,{status:0}),allPages(api.clues,{status:1})]).then((sets)=>sets.flat().sort((a,b)=>b.risk_level-a.risk_level || b.total_score-a.total_score || a.create_at.localeCompare(b.create_at)).slice(0,5)) : [],
    auth.canBlock('overview.risk') ? api.regionRisk({risk_level:3,size:1}) : {total:0},
  ])
  const regional = batches.filter((b)=>b.judge_object===1).sort(byNewest)
  if (!regional.some((b)=>b.batch_id===batchId.value)) batchId.value=regional[0]?.batch_id || ''
  if (auth.canBlock('overview.risk')) await loadRisk()
  updatedAt.value=toDateTime(new Date())
  return {ov,batches:regional,pending,regionalHigh:highRisk.total}
})
const batch = computed(()=>summary.data.value?.batches.find((b)=>b.batch_id===batchId.value))
const rule = computed(()=>dicts.value?.rules.find((r)=>r.rule_id===batch.value?.rule_id))
const entries=computed(()=>[{name:'features',page:'features',title:'特征清单'},{name:'ops',page:'ops',title:'版本与批次'},{name:'cases',page:'cases',title:'历史案件'},{name:'audit',page:'audit',title:'审计日志'},{name:'admin',page:'admin',title:'系统管理'}].filter((e)=>auth.canPage(e.page)))
function loadRisk(){ return risk.run() }
function refresh(){ return summary.run() }
function goClues(status){router.push({name:'clues',query:{status}})}
</script>
<style scoped>
.heading-range { display:flex; align-items:center; flex-wrap:wrap; gap:8px; margin-left:auto; }.heading-range label { font-size:13px; color:var(--text-muted); }.heading-range .el-select { width:220px; }.chart-mode { display:flex; gap:8px; margin-bottom:20px; }.view-tab { display:flex; align-items:center; justify-content:center; gap:8px; width:44px; min-height:36px; overflow:hidden; background:transparent; border:1px solid #d8e0ea; border-radius:8px; color:#475569; cursor:pointer; transition:width .2s ease-out; white-space:nowrap; }.view-tab.active { width:124px; color:#1d4ed8; background:#eff6ff; border-color:#94b2f5; }
.scope-bar { display:flex; align-items:center; flex-wrap:wrap; gap:12px 24px; color:var(--text-muted); font-size:13px; margin-bottom:16px; }
.batch-scope { margin-top:24px; padding:16px; background:#fff; border:1px solid var(--card-border); border-radius:12px; }
.batch-scope .el-select { width:230px; }
.hero-workspace { display:grid; grid-template-columns:repeat(12,minmax(0,1fr)); gap:20px; margin-bottom:24px; }.hero-workspace > .el-card { grid-column:span 8; grid-row:span 2; }.hero-workspace > .work-stats { grid-column:span 4; grid-row:span 2; grid-template-columns:repeat(2,minmax(0,1fr)); align-content:stretch; }.hero-workspace > .el-card :deep(.heat-scroll) { min-height:300px; }
.overview-support { display:flex; gap:20px; flex-wrap:wrap; margin-top:20px; }
.overview-support > * { flex:1; min-width:min(100%,280px); }
.work-stats { grid-template-columns:repeat(4,minmax(0,1fr)); }
.action-stat { text-align:left; font:inherit; cursor:pointer; display:flex; flex-direction:column; }
.action-stat:hover { border-color:var(--el-color-primary); background:#f8fbff; }
.warn { color:var(--level-mid); }.high { color:var(--level-high); }
.card-title { justify-content:space-between; }.card-title a { font-size:13px; font-weight:400; }
.card-sub { font-size:13px; line-height:1.6; margin:8px 0 0; }
.todo-list { display:grid; grid-template-columns:repeat(auto-fit,minmax(230px,1fr)); gap:20px; }.todo-row { display:block; padding:16px 0; color:inherit; border-bottom:1px solid var(--card-border); text-decoration:none; }
.todo-row:first-child { padding-top:0; }.todo-row:last-child { border:0; padding-bottom:0; }
.todo-row:hover .todo-title { color:var(--el-color-primary); }.todo-title { display:flex; justify-content:space-between; gap:12px; font-weight:600; }
.todo-meta { display:flex; flex-wrap:wrap; gap:8px; margin:10px 0; font-size:13px; }.todo-row > .mono { font-size:12px; }
.eval-summary { display:flex; flex-wrap:wrap; gap:16px 28px; }.eval-summary b { margin-left:8px; }
.entries { display:flex; flex-wrap:wrap; gap:12px; }.entries .el-button { margin:0; }
@media(max-width:1100px){.hero-workspace{grid-template-columns:minmax(0,1fr)}.hero-workspace > .el-card,.hero-workspace > .work-stats{grid-column:auto;grid-row:auto}.hero-workspace > .work-stats{grid-template-columns:repeat(4,minmax(0,1fr))} }
@media(max-width:700px){.hero-workspace > .work-stats{grid-template-columns:repeat(2,minmax(0,1fr))}.batch-scope .el-select{width:100%} }
</style>
