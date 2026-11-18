<template>
  <AsyncState :loading="loading" :error="error" :data="data" :empty="!!data && !data.areas.length" @retry="run">
    <EChart v-if="option" :option="option" height="350px" @click="open" />
    <p class="muted">示例区域坐标 · 每个区域取当前批次的峰值评分；灰色为本批次无评分。</p>
    <div class="area-links"><router-link v-for="r in peaks" :key="r.area_id" :to="{name:'risk-detail',params:{scoreId:r.score_id}}">{{ r.area_name }} · {{ fixed(r.total_score) }} 分</router-link></div>
  </AsyncState>
</template>
<script setup>
import {computed} from 'vue'
import {useRouter} from 'vue-router'
import {api} from '@/api'
import {useAsync} from '@/composables/useAsync'
import {fixed} from '@/utils/format'
import {escapeHtml} from '@/utils/dashboard'
import AsyncState from './AsyncState.vue'
import EChart from './EChart.vue'
const props=defineProps({rows:{type:Array,default:()=>[]}})
const router=useRouter()
const {data,loading,error,run}=useAsync(()=>api.riskMap())
const peaks=computed(()=>{
  const map=new Map()
  for(const row of props.rows)if(!map.has(row.area_id)||map.get(row.area_id).total_score<row.total_score)map.set(row.area_id,row)
  return [...map.values()].sort((a,b)=>b.total_score-a.total_score)
})
const option=computed(()=>{
  const areas=data.value?.areas
  if(!areas?.length)return null
  const lng=areas.map((a)=>a.lng),lat=areas.map((a)=>a.lat)
  return {tooltip:{formatter:(p)=>`${escapeHtml(p.data.area.area_name)}<br/>${p.data.row?`${fixed(p.data.row.total_score)} 分 · ${p.data.row.risk_level_name}风险`:'本批次无评分'}`},
    grid:{left:28,right:28,top:20,bottom:40},xAxis:{type:'value',show:false,min:Math.min(...lng)-.018,max:Math.max(...lng)+.018},yAxis:{type:'value',show:false,min:Math.min(...lat)-.018,max:Math.max(...lat)+.018},
    series:[{type:'scatter',symbolSize:26,label:{show:true,position:'bottom',distance:7,formatter:(p)=>p.data.area.area_name,color:'#475569',fontSize:12},labelLayout:{hideOverlap:true},data:areas.map((a)=>{const row=peaks.value.find((r)=>r.area_id===a.area_id);return {value:[a.lng,a.lat],area:a,row,itemStyle:{color:row?({1:'#cbd5e1',2:'#f3d19e',3:'#d03050'})[row.risk_level]:'#e5e7eb'}}})}]}
})
function open(p){if(p.data?.row)router.push({name:'risk-detail',params:{scoreId:p.data.row.score_id}})}
</script>
<style scoped>
p{font-size:13px;line-height:1.7}.area-links{display:flex;flex-wrap:wrap;gap:12px 20px;font-size:13px}
</style>
