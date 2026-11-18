<template>
  <div class="page">
    <div class="page-head"><div><h2>示例区域风险分布</h2><p class="sub">按区域以红色深浅展示风险等级（颜色越深风险越高），拖动时间轴查看各观察夜的风险分布变化。坐标取自区域表 area_info 的经纬度字段。</p></div><el-tag type="info" effect="plain">{{ areas.length }} 个区域 · {{ dates.length }} 个观察夜</el-tag></div>
    <AsyncState :loading="loading" :error="error" :data="mapData" :empty="!!mapData && !areas.length" empty-text="暂无区域坐标或风险数据" @retry="load">
      <el-card v-if="mapData" shadow="never">
        <template #header><div class="card-title">区域风险分布<span class="hint">示例城市（虚构）· 坐标为示例值，仅用于教学演示</span></div></template>
        <div v-if="dates.length" class="timeline">
          <div class="timeline-head"><label for="map-date">观察夜</label><el-select id="map-date" :model-value="currentIdx" aria-label="选择观察夜" @change="selectDate"><el-option v-for="(d,i) in dates" :key="d" :label="d" :value="i" /></el-select><el-button :icon="playing ? VideoPause : VideoPlay" :disabled="dates.length<2" @click="playing ? pause() : play()">{{ playing ? '暂停' : '播放' }}</el-button><span class="muted" role="status">参与研判 {{ activeCount }} 个区域</span></div>
          <el-slider id="map-timeline" v-model="currentIdx" :min="0" :max="Math.max(1,dates.length-1)" :disabled="dates.length<2" :step="1" :marks="dateMarks" :format-tooltip="dateLabel" aria-label="观察夜时间轴" @change="pause" />
        </div>
        <el-empty v-else description="暂无观察夜风险评分" />
        <div class="map-workspace">
          <div class="map-canvas"><EChart v-if="chartOption" :option="chartOption" height="460px" @click="selectPoint" /><div class="legend"><span class="gradient-bar" /><span>低分 → 高分</span><i class="gray-dot" /><span>当夜无研判数据</span></div></div>
          <section class="area-ranking" aria-label="区域风险排行"><h3>区域风险排行</h3><p class="muted">按当夜峰值分数排列，点击区域查看依据</p><button v-for="(a,i) in rankedAreas" :key="a.area_id" class="area-row" :class="{'is-selected':selectedId===a.area_id}" :aria-pressed="selectedId===a.area_id" @click="selectedId=a.area_id"><span class="rank-num num">{{ i+1 }}</span><span class="area-name">{{ a.area_name }}<small>{{ a.risk ? `样本 ${a.risk.sample_size}` : '当夜无研判数据' }}</small></span><span class="area-value"><b class="num">{{ a.risk ? fixed(a.risk.total_score) : '—' }}</b><LevelTag v-if="a.risk" :level="a.risk.risk_level" /></span></button></section>
        </div>
        <section v-if="selectedArea" class="selection-panel" aria-live="polite"><div class="selection-head"><div><h3>{{ selectedArea.area_name }}</h3><p class="muted">{{ currentDate || '暂无观察夜' }} · {{ selectedArea.area_type_name }}</p></div><LevelTag v-if="selectedArea.risk" :level="selectedArea.risk.risk_level" /></div><template v-if="selectedArea.risk"><div class="selection-facts"><span>峰值总分 <b>{{ fixed(selectedArea.risk.total_score) }}</b></span><span>命中特征 {{ selectedArea.risk.hit_cnt }} 项</span><span>样本量 {{ selectedArea.risk.sample_size }}</span><span class="mono">{{ selectedArea.risk.batch_id }}</span></div><div class="toolbar"><router-link v-if="selectedArea.risk.score_id != null" :to="{name:'risk-detail',params:{scoreId:selectedArea.risk.score_id}}">查看命中依据 →</router-link><router-link :to="{name:'risk',query:{area_id:selectedId,batch_id:selectedArea.risk.batch_id}}">查看区域评分 →</router-link><router-link v-if="auth.canPage('clues')" :to="{name:'clues',query:{area_id:selectedId}}">查看该区域线索（全部时段） →</router-link></div></template><p v-else class="muted">该区域当夜无研判数据，可切换观察夜查看。</p></section>
      </el-card>
    </AsyncState>
  </div>
</template>
<script setup>
import {computed,onBeforeUnmount,ref,watch} from 'vue'
import {VideoPause,VideoPlay} from '@element-plus/icons-vue'
import {api} from '@/api'
import {useAsync} from '@/composables/useAsync'
import {useAuthStore} from '@/stores/auth'
import {fixed} from '@/utils/format'
import {escapeHtml} from '@/utils/dashboard'
import AsyncState from '@/components/AsyncState.vue'
import EChart from '@/components/EChart.vue'
import LevelTag from '@/components/LevelTag.vue'
const auth=useAuthStore()
const {data:mapData,loading,error,run:load}=useAsync(()=>api.riskMap())
const areas=computed(()=>mapData.value?.areas || []), dates=computed(()=>mapData.value?.dates || [])
const currentIdx=ref(0),selectedId=ref(''),playing=ref(false)
let timer=null
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
function riskColor(score){if(score==null || Number.isNaN(score))return '#e5e7eb';const t=Math.max(0,Math.min(1,score/9));return `rgb(${Math.round(253-99*t)},${Math.round(232-214*t)},${Math.round(232-214*t)})`}
const chartOption=computed(()=>{
  if(!areas.value.length)return null
  const lngs=areas.value.map((a)=>a.lng),lats=areas.value.map((a)=>a.lat)
  return {tooltip:{formatter:(p)=>{const a=p.data.area,r=p.data.risk;return `${escapeHtml(a.area_name)}<br/>${r ? `${r.risk_level_name}风险 · ${fixed(r.total_score)} 分<br/>样本 ${r.sample_size} · 命中 ${r.hit_cnt} 项` : '当夜无研判数据'}`}},grid:{left:32,right:32,top:30,bottom:48},
    xAxis:{type:'value',min:Math.min(...lngs)-.018,max:Math.max(...lngs)+.018,show:false},yAxis:{type:'value',min:Math.min(...lats)-.018,max:Math.max(...lats)+.018,show:false},
    series:[{type:'scatter',symbolSize:30,data:areas.value.map((a)=>{const r=riskByArea.value[a.area_id] || null;return {value:[a.lng,a.lat],area:a,risk:r,itemStyle:{color:riskColor(r?.total_score),borderWidth:selectedId.value===a.area_id?3:1,borderColor:selectedId.value===a.area_id?'#2563eb':'#fff'}}}),label:{show:true,position:'bottom',distance:8,formatter:(p)=>p.data.area.area_name,color:'#475569',fontSize:12},labelLayout:{hideOverlap:true}}]}
})
function selectPoint(p){if(p.data?.area){pause();selectedId.value=p.data.area.area_id}}
function selectDate(i){pause();currentIdx.value=i}
function play(){if(playing.value || dates.value.length<2)return;playing.value=true;timer=setInterval(()=>{currentIdx.value=(currentIdx.value+1)%dates.value.length},1600)}
function pause(){playing.value=false;if(timer){clearInterval(timer);timer=null}}
onBeforeUnmount(pause)
</script>
<style scoped>
.timeline{padding:0 12px 20px;margin-bottom:12px;border-bottom:1px solid var(--card-border)}.timeline-head{display:flex;flex-wrap:wrap;align-items:center;gap:12px;margin-bottom:6px}.timeline-head .el-select{width:170px}.timeline-head .muted{font-size:13px}
.map-workspace{display:grid;grid-template-columns:minmax(0,1.8fr) minmax(270px,1fr);gap:24px}.map-canvas{min-width:0}.legend{display:flex;flex-wrap:wrap;align-items:center;gap:10px;font-size:12px;color:var(--text-muted);margin:8px 0 16px}.gradient-bar{width:120px;height:12px;border-radius:4px;background:linear-gradient(to right,#fde8e8,#9a1212)}.gray-dot{width:12px;height:12px;border-radius:50%;background:#e5e7eb;margin-left:12px}
.area-ranking{max-height:510px;overflow:auto;padding:0 6px}.area-ranking h3,.selection-head h3{margin:0;font-size:16px}.area-ranking > p{font-size:13px;line-height:1.5}.area-row{width:100%;background:transparent;border:0;border-bottom:1px solid var(--card-border);display:flex;align-items:center;gap:12px;text-align:left;padding:12px 8px;cursor:pointer;color:inherit;font:inherit}.area-row:hover,.area-row.is-selected{background:#eff6ff}.rank-num{color:var(--text-muted);width:20px}.area-name{flex:1}.area-name small{display:block;color:var(--text-muted);font-size:12px;margin-top:6px}.area-value{text-align:right;display:flex;flex-direction:column;align-items:flex-end;gap:6px}
.selection-panel{margin-top:24px;padding:20px;background:#f8fafc;border-radius:12px}.selection-head{display:flex;align-items:center;justify-content:space-between;gap:12px}.selection-head p{margin:8px 0;font-size:13px}.selection-facts{display:flex;flex-wrap:wrap;gap:12px 28px;margin:12px 0 20px;font-size:14px}.selection-panel .toolbar{gap:16px 24px}
@media(max-width:1000px){.map-workspace{grid-template-columns:minmax(0,1fr)}.area-ranking{max-height:320px}.selection-panel{padding:16px}}
</style>
