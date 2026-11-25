<template>
  <div class="page"><div class="page-head"><div><h2>人员风险</h2><p class="sub">每人最新观察时段的风险指数，结合事件流水核查。</p></div><el-input v-model="filters.person_id" placeholder="人员编号，如 P0001" clearable style="width:240px" @change="reload" /></div>
    <div class="people-workspace"><el-card shadow="never"><template #header><div class="card-title">人员列表<span class="hint">最新时段 · 0–100</span></div></template><AsyncState :data="data" :loading="loading" :error="error" @retry="load"><el-table v-if="data" :data="data.list" highlight-current-row @row-click="select"><el-table-column prop="person_id" label="人员" width="95" /><el-table-column label="指数" width="85"><template #default="{row}">{{ fixed(row.total_score) }}</template></el-table-column><el-table-column label="等级" width="90"><template #default="{row}"><LevelTag :level="row.risk_level" /></template></el-table-column><el-table-column prop="area_name" label="区域" min-width="120" /><el-table-column label="详情" width="75"><template #default="{row}"><el-button link type="primary" @click.stop="select(row)">查看</el-button></template></el-table-column></el-table><el-pagination v-if="data" v-model:current-page="filters.page" :total="data.total" :page-size="20" layout="prev,pager,next" @current-change="load" /></AsyncState></el-card>
    <section v-if="selected" class="person-detail"><el-card shadow="never"><template #header><div class="card-title"><span class="mono">{{ selected.person_id }}</span><router-link :to="{name:'risk-detail',params:{scoreId:selected.score_id}}">评分解释 →</router-link></div></template><p>观察时段 {{ selected.window_start }} · 关联区域 {{ selected.area_name }}</p><EChart :option="chart" height="230px" /><p class="muted small">横轴：北京时间；纵轴：风险指数（0–100）。同一时段取最新成功批次。</p></el-card>
      <el-card shadow="never"><template #header><div class="card-title">事件流水<span class="hint">车辆归属关联需核实驾驶人</span></div></template><el-date-picker v-model="dateRange" type="daterange" value-format="YYYY-MM-DD" range-separator="至" start-placeholder="起始日期" end-placeholder="结束日期" @change="reloadTimeline" /><AsyncState :data="timeline.data.value" :loading="timeline.loading.value" :error="timeline.error.value" @retry="timeline.run"><el-timeline v-if="timeline.data.value" class="person-timeline"><el-timeline-item v-for="e in timeline.data.value.list" :key="`${e.kind}:${e.source_id}`" :timestamp="e.event_at" placement="top" :type="e.certainty==='association'?'warning':'primary'"><div>{{ e.description }}</div><span class="mono muted small">{{ e.kind }} #{{ e.source_id }}</span></el-timeline-item></el-timeline><el-pagination v-if="timeline.data.value" v-model:current-page="timelinePage" :total="timeline.data.value.total" :page-size="20" layout="prev,pager,next" @current-change="timeline.run" /></AsyncState></el-card></section>
    <el-card v-else shadow="never"><el-empty description="选择一位人员，查看风险变化与事件流水" /></el-card></div>
  </div>
</template>
<script setup>
import {computed,reactive,ref,watch} from 'vue'
import {useRoute} from 'vue-router'
import {api} from '@/api'
import {useAsync} from '@/composables/useAsync'
import {fixed,halfOpenRange} from '@/utils/format'
import AsyncState from '@/components/AsyncState.vue'
import LevelTag from '@/components/LevelTag.vue'
import EChart from '@/components/EChart.vue'
const route=useRoute(),selected=ref(null),dateRange=ref([]),timelinePage=ref(1)
const filters=reactive({person_id:route.query.person_id||'',page:1,size:20})
const {data,loading,error,run:load}=useAsync(()=>api.people({...filters}))
const trend=useAsync(()=>selected.value?api.trends({person_id:selected.value.person_id,version_id:selected.value.version_id}):Promise.resolve([]),{immediate:false})
const timeline=useAsync(()=>selected.value?api.personTimeline(selected.value.person_id,{...halfOpenRange(dateRange.value),page:timelinePage.value,size:20}):Promise.resolve({list:[],total:0}),{immediate:false})
function reload(){filters.page=1;load()}
function select(row){selected.value=row;timelinePage.value=1;trend.run();timeline.run()}
watch(data,d=>{if(filters.person_id&&d?.list.length)select(d.list[0])})
function reloadTimeline(){timelinePage.value=1;timeline.run()}
const chart=computed(()=>({tooltip:{trigger:'axis'},grid:{left:45,right:20,top:30,bottom:35},xAxis:{type:'category',name:'时间',data:(trend.data.value||[]).map(r=>r.window_start.slice(5,16))},yAxis:{type:'value',name:'风险指数',min:0,max:100},series:[{type:'line',showSymbol:false,connectNulls:false,data:(trend.data.value||[]).map(r=>r.total_score),lineStyle:{color:'#345fc5'}}]}))
</script>
<style scoped>
.people-workspace{display:grid;grid-template-columns:minmax(360px,1fr) minmax(0,1.35fr);gap:24px;align-items:start}.person-detail{display:grid;gap:24px}.person-timeline{padding:24px 0 0 8px}.small{font-size:12px;line-height:1.8}.el-pagination{margin-top:20px}@media(max-width:1000px){.people-workspace{grid-template-columns:minmax(0,1fr)}}
</style>
