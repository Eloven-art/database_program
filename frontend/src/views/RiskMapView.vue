<template>
  <div class="map-page">
    <AsyncState :loading="loading" :error="error" :data="mapData" :empty="!!mapData && !areas.length" empty-text="暂无区域坐标或风险数据" @retry="load">
      <div v-if="mapData" class="map-canvas">
        <EChart v-if="chartOption" :option="chartOption" height="100%" @click="selectPoint" />
        <header class="floating map-heading">
          <h2>示例区域风险分布</h2>
          <div class="map-range"><el-select :model-value="currentIdx" aria-label="选择观察夜" @change="selectDate"><el-option v-for="(d,i) in dates" :key="d" :label="d" :value="i" /></el-select><span class="muted">{{ activeCount }} / {{ areas.length }} 个区域有评分</span></div>
          <details><summary>技术说明与示例范围</summary><p>按区域以红色深浅展示风险等级（颜色越深风险越高），拖动时间轴查看各观察夜的风险分布变化。坐标取自区域表 area_info 的经纬度字段。</p><p>示例城市（虚构）· 坐标为示例值，仅用于教学演示。</p></details>
        </header>
        <div class="map-tools" role="toolbar" aria-label="地图快捷工具">
          <el-tooltip content="刷新地图" placement="left"><el-button :icon="Refresh" :loading="loading" type="primary" aria-label="刷新地图" @click="pause();load()" /></el-tooltip>
          <el-tooltip content="区域排行" placement="left"><el-button :icon="Sort" :aria-pressed="rankingOpen" aria-label="切换区域排行" @click="rankingOpen=!rankingOpen" /></el-tooltip>
          <el-tooltip content="风险图例" placement="left"><el-button :icon="InfoFilled" :aria-pressed="legendOpen" aria-label="切换风险图例" @click="legendOpen=!legendOpen" /></el-tooltip>
          <el-tooltip content="恢复最近观察夜" placement="left"><el-button :icon="Aim" aria-label="恢复最近观察夜" @click="resetView" /></el-tooltip>
        </div>
        <aside v-if="rankingOpen" class="floating ranking-panel" aria-label="区域风险排行">
          <div class="panel-title"><h3>区域风险排行</h3><el-button text aria-label="关闭区域排行" @click="rankingOpen=false"><el-icon><Close /></el-icon></el-button></div>
          <p class="muted">按当夜峰值分数排列，点击区域查看依据</p>
          <div class="ranking-scroll"><button v-for="(a,i) in rankedAreas" :key="a.area_id" class="area-row" :class="{'is-selected':selectedId===a.area_id}" :aria-pressed="selectedId===a.area_id" @click="selectArea(a.area_id)"><span class="rank-num num">{{ i+1 }}</span><span class="area-name">{{ a.area_name }}<small>{{ a.risk ? `样本 ${a.risk.sample_size}` : '当夜无研判数据' }}</small></span><span class="area-value"><b class="num">{{ a.risk ? fixed(a.risk.total_score) : '—' }}</b><LevelTag v-if="a.risk" :level="a.risk.risk_level" /></span></button></div>
        </aside>
        <aside v-if="legendOpen" class="floating legend-panel"><div class="panel-title"><h3>风险图例</h3><el-button text aria-label="关闭风险图例" @click="legendOpen=false"><el-icon><Close /></el-icon></el-button></div><div class="legend"><span class="gradient-bar" /><span>0分 → 9分及以上</span><i class="gray-dot" /><span>当夜无研判数据</span></div></aside>
        <section v-if="selectedArea" class="floating selection-panel" aria-live="polite">
          <div class="selection-head"><div><h3>{{ selectedArea.area_name }}</h3><p class="muted">{{ currentDate || '暂无观察夜' }} · {{ selectedArea.area_type_name }}</p></div><LevelTag v-if="selectedArea.risk" :level="selectedArea.risk.risk_level" /><el-button text :aria-expanded="detailOpen" aria-label="展开或收起区域详情" @click="detailOpen=!detailOpen"><el-icon><component :is="detailOpen ? 'ArrowDown' : 'ArrowUp'" /></el-icon></el-button></div>
          <div v-if="detailOpen"><template v-if="selectedArea.risk"><div class="selection-facts"><span>峰值 <b>{{ fixed(selectedArea.risk.total_score) }}</b> 分</span><span>命中 {{ selectedArea.risk.hit_cnt }} 项</span><span>样本 {{ selectedArea.risk.sample_size }}</span></div><div class="toolbar"><router-link v-if="selectedArea.risk.score_id != null" :to="{name:'risk-detail',params:{scoreId:selectedArea.risk.score_id}}">命中依据 →</router-link><router-link :to="{name:'risk',query:{area_id:selectedId,batch_id:selectedArea.risk.batch_id}}">区域评分 →</router-link><router-link v-if="auth.canPage('clues')" :to="{name:'clues',query:{area_id:selectedId}}">区域线索（全部时段） →</router-link></div><p class="mono muted batch-label">{{ selectedArea.risk.batch_id }}</p></template><p v-else class="muted">该区域当夜无研判数据，可切换观察夜查看。</p></div>
        </section>
        <section class="floating timeline-panel" aria-label="观察夜时间轴">
          <el-button :icon="playing ? VideoPause : VideoPlay" :disabled="dates.length<2" @click="playing ? pause() : play()">{{ playing ? '暂停' : '播放' }}</el-button>
          <div class="timeline-slider"><el-slider v-model="currentIdx" :min="0" :max="Math.max(1,dates.length-1)" :disabled="dates.length<2" :step="1" :marks="dateMarks" :format-tooltip="dateLabel" aria-label="观察夜时间轴" @change="pause" /></div><span class="num">{{ currentDate || '暂无观察夜' }}</span>
        </section>
      </div>
    </AsyncState>
  </div>
</template>
<script setup>
import {computed,onBeforeUnmount,ref,watch} from 'vue'
import {VideoPause,VideoPlay,Refresh,Sort,InfoFilled,Aim} from '@element-plus/icons-vue'
import {api} from '@/api'
import {useAsync} from '@/composables/useAsync'
import {useAuthStore} from '@/stores/auth'
import {fixed} from '@/utils/format'
import {chartPalette} from '@/styles/chart-theme'
import {escapeHtml} from '@/utils/dashboard'
import AsyncState from '@/components/AsyncState.vue'
import EChart from '@/components/EChart.vue'
import LevelTag from '@/components/LevelTag.vue'
const auth=useAuthStore()
const {data:mapData,loading,error,run:load}=useAsync(()=>api.riskMap())
const areas=computed(()=>mapData.value?.areas || []), dates=computed(()=>mapData.value?.dates || [])
const currentIdx=ref(0),selectedId=ref(''),playing=ref(false)
const rankingOpen=ref(window.innerWidth > 1000), legendOpen=ref(false), detailOpen=ref(true)
let timer=null
function resetView(){pause();currentIdx.value=Math.max(0,dates.value.length-1);selectedId.value=rankedAreas.value[0]?.area_id || '';detailOpen.value=true}
function selectArea(id){pause();selectedId.value=id;detailOpen.value=true}
watch(dates,(d,old)=>{if(d.length && !old?.length)currentIdx.value=d.length-1})
const currentDate=computed(()=>dates.value[currentIdx.value] || '')
const currentRisk=computed(()=>mapData.value?.risk.find((r)=>r.date===currentDate.value))
const riskByArea=computed(()=>Object.fromEntries((currentRisk.value?.areas || []).map((a)=>[a.area_id,a])))
const activeCount=computed(()=>currentRisk.value?.areas.length || 0)
const rankedAreas=computed(()=>areas.value.map((a)=>({...a,risk:riskByArea.value[a.area_id]})).sort((a,b)=>(b.risk?.total_score ?? -Infinity)-(a.risk?.total_score ?? -Infinity) || a.area_id.localeCompare(b.area_id)))
const selectedArea=computed(()=>rankedAreas.value.find((a)=>a.area_id===selectedId.value))
watch(rankedAreas,(rows)=>{if(!rows.some((a)=>a.area_id===selectedId.value))selectedId.value=rows[0]?.area_id || ''},{immediate:true})
const dateLabel=(i)=>dates.value[i] || ''
const dateMarks=computed(()=>{
  const ids=[0,Math.floor((dates.value.length-1)/2),dates.value.length-1].filter((i)=>i>=0)
  return Object.fromEntries([...new Set(ids)].map((i)=>[i,dates.value[i]?.slice(5)]))
})
function riskColor(score){if(score==null || Number.isNaN(score))return chartPalette.blank;const t=Math.max(0,Math.min(1,score/9));return `rgb(${Math.round(244-76*t)},${Math.round(228-164*t)},${Math.round(222-165*t)})`}
const chartOption=computed(()=>{
  if(!areas.value.length)return null
  const lngs=areas.value.map((a)=>a.lng),lats=areas.value.map((a)=>a.lat)
  return {tooltip:{formatter:(p)=>{const a=p.data.area,r=p.data.risk;return `${escapeHtml(a.area_name)}<br/>${r ? `${r.risk_level_name}风险 · ${fixed(r.total_score)} 分<br/>样本 ${r.sample_size} · 命中 ${r.hit_cnt} 项` : '当夜无研判数据'}`}},grid:{left:40,right:rankingOpen.value && window.innerWidth>1000 ? 330 : 40,top:175,bottom:detailOpen.value ? 320 : 135},
    xAxis:{type:'value',min:Math.min(...lngs)-.018,max:Math.max(...lngs)+.018,show:false},yAxis:{type:'value',min:Math.min(...lats)-.018,max:Math.max(...lats)+.018,show:false},
    series:[{type:'scatter',symbolSize:22,data:areas.value.map((a)=>{const r=riskByArea.value[a.area_id] || null;return {value:[a.lng,a.lat],area:a,risk:r,itemStyle:{color:riskColor(r?.total_score),borderWidth:selectedId.value===a.area_id?2:1,borderColor:selectedId.value===a.area_id?chartPalette.accent:'#aebbb2'}}}),label:{show:true,position:'bottom',distance:8,formatter:(p)=>p.data.area.area_name,color:chartPalette.muted,fontSize:12},labelLayout:{hideOverlap:true}}]}
})
function selectPoint(p){if(p.data?.area){pause();selectArea(p.data.area.area_id)}}
function selectDate(i){pause();currentIdx.value=i}
function play(){if(playing.value || dates.value.length<2)return;playing.value=true;timer=setInterval(()=>{currentIdx.value=(currentIdx.value+1)%dates.value.length},1600)}
function pause(){playing.value=false;if(timer){clearInterval(timer);timer=null}}
onBeforeUnmount(pause)
</script>
<style scoped>
.map-page { height:100%; min-height:680px; }.map-page :deep(> div),.map-page :deep(.el-loading-parent--relative) { height:100%; }.map-canvas { position:relative; height:100%; min-height:680px; background:#eef0eb; overflow:hidden; }.floating { position:absolute; background:#ffffff; border-radius:14px; box-shadow:0 4px 20px #20282e10; padding:20px; }.map-heading { top:16px; left:16px; width:min(480px,calc(100% - 96px)); background:#ffffff; }.map-heading h2 { margin:0 0 12px; font-size:28px; font-weight:500; }.map-range { display:flex; gap:12px; align-items:center; flex-wrap:wrap; font-size:13px; }.map-range .el-select { width:160px; }details { margin-top:12px; font-size:12px; color:var(--text-muted); }summary { cursor:pointer; }details p { line-height:1.7; max-width:65ch; }
.map-tools { position:absolute; top:16px; right:16px; display:flex; flex-direction:column; gap:8px; }.map-tools .el-button { width:44px; height:44px; margin:0; box-shadow:0 1px 4px #20282e0d; }
.panel-title,.selection-head { display:flex; align-items:center; gap:8px; justify-content:space-between; }h3 { font-size:16px; font-weight:500; margin:0; }.ranking-panel { top:16px; right:76px; width:280px; max-height:calc(100% - 160px); display:flex; flex-direction:column; }.ranking-panel > p { font-size:12px; line-height:1.6; margin:8px 0; }.ranking-scroll { overflow:auto; }.area-row { display:flex; width:100%; align-items:center; gap:8px; padding:12px 4px; background:transparent; border:0; border-bottom:1px solid var(--card-border); color:inherit; font:inherit; text-align:left; cursor:pointer; }.area-row:hover,.area-row.is-selected { background:#f0f3ee; }.rank-num { width:16px; color:var(--text-muted); }.area-name { flex:1; }.area-name small { display:block; margin-top:5px; font-size:12px; color:var(--text-muted); }.area-value { display:flex; flex-direction:column; align-items:flex-end; gap:4px; }
.selection-panel { bottom:126px; left:16px; width:min(460px,calc(100% - 32px)); }.selection-head p { font-size:12px; margin:6px 0 0; }.selection-facts { display:flex; gap:18px; flex-wrap:wrap; margin:14px 0; }.selection-panel .toolbar { gap:12px; font-size:13px; }.batch-label { margin:12px 0 0; font-size:12px; }.timeline-panel { bottom:16px; left:16px; right:16px; display:flex; align-items:center; gap:24px; min-height:88px; }.timeline-slider { flex:1; min-width:0; padding:0 12px 18px; }.timeline-panel > span { font-size:13px; }.legend-panel { right:76px; bottom:126px; width:260px; }.legend { display:flex; gap:8px; flex-wrap:wrap; align-items:center; margin-top:12px; font-size:12px; }.gradient-bar { width:100%; height:10px; background:linear-gradient(to right,#f4e4de,#a84039); }.gray-dot { width:12px; height:12px; background:#dce1dd; border-radius:50%; }
@media(max-width:1000px) { .ranking-panel { top:180px; right:16px; max-height:300px; z-index:2; }.legend-panel { right:16px; bottom:126px; z-index:3; } }
@media(max-width:600px) { .map-heading h2 { font-size:23px; }.map-heading { width:calc(100% - 88px); padding:12px; }.timeline-panel { gap:12px; padding:12px; }.timeline-panel > span { display:none; }.selection-panel { padding:12px; }.map-page,.map-canvas { min-height:720px; }.map-page { overflow:auto; } }
</style>

<style scoped>
.ranking-panel .area-row { min-height:72px; border-radius:6px; }.rank-num { font-family:var(--font-mono); font-size:11px; }.area-value b { font-family:var(--font-data); font-size:20px; font-weight:500; }.area-name { font-size:13px; }.panel-title .el-button { width:32px; min-height:32px; padding:4px; }.map-heading details { border-top:1px solid var(--card-border); padding-top:12px; }.selection-facts b { font-family:var(--font-data); font-size:24px; font-weight:500; }.timeline-panel > span { font-family:var(--font-mono); }.map-tools .el-button { border-color:var(--card-border); }.selection-panel .toolbar { gap:12px 16px; }
</style>
