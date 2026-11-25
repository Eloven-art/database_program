<template>
  <section class="replay-filter" aria-label="线索回放筛选">
    <div class="replay-filter-head"><h2>线索时空回放</h2><span>区域级定位</span></div>
    <div class="replay-filters"><el-date-picker v-model="day" type="date" value-format="YYYY-MM-DD" :clearable="false" aria-label="回放日期" @change="reload" /><el-select v-model="area" clearable placeholder="全部区域" aria-label="筛选回放区域" @change="reload"><el-option v-for="a in areas" :key="a.area_id" :label="a.area_name" :value="a.area_id" /></el-select></div>
    <el-input v-model="person" placeholder="人员编号（可选）" clearable aria-label="筛选回放人员" @change="reload" @keyup.enter="reload" />
    <div class="replay-scope"><button :aria-pressed="!single" @click="setScope(false)">总览回放</button><button :aria-pressed="single" :disabled="!chosen" @click="setScope(true)">单条事件链</button></div>
    <p>{{ single ? '同人员同事件 · 按证据节点发生时间' : '跨事件虚线仅表示浏览顺序' }} · <button class="plain" @click="reload">刷新</button></p>
  </section>
  <aside class="replay-events" aria-label="回放事件列表">
    <div class="replay-panel-heading"><h3>{{ single ? '选择关联事件' : '按时间排列的事件' }}</h3><span>{{ rows.length }} 条</span><button class="plain collapse-list" :aria-expanded="listOpen" @click="listOpen=!listOpen">{{ listOpen?'收起':'展开' }}</button></div>
    <p v-if="loading" role="status">正在读取线索快照…</p><p v-else-if="error" role="alert">{{ error }} <button @click="reload">重试</button></p><p v-else-if="!rows.length">所选范围暂无线索事件，请调整日期或筛选。</p>
    <div v-if="listOpen" class="replay-list"><button v-for="(event,i) in rows" :key="event.chain_id" class="replay-event-row" :class="{selected:single?chosen?.chain_id===event.chain_id:index===i}" :aria-pressed="single?chosen?.chain_id===event.chain_id:index===i" @click="chooseEvent(event,i)"><span class="event-time">{{ event.event_at.slice(11,16) }}<small v-if="i && rows[i-1].event_at===event.event_at">同时发生</small></span><span><strong>{{ event.area_name }}</strong><small>{{ event.person_id }} · {{ event.place_name }}</small></span><span class="event-score">{{ fixed(event.total_score) }}<small>{{ event.snapshot_count }} 份快照合并</small></span></button></div>
  </aside>
  <section class="replay-detail" aria-live="polite" aria-label="当前回放线索">
    <template v-if="active"><div class="replay-panel-heading"><h3>{{ active.title || '消费事件线索' }}</h3><span>{{ index+1 }} / {{ events.length }}</span></div><p class="detail-time">{{ active.event_at }} <span v-if="index>0 && events[index-1].event_at===active.event_at">· 同时发生</span></p>
      <p class="detail-location">{{ active.area_name || (active.area_id?areaName(active.area_id):'信息节点 · 无地理落点') }}</p>
      <p>{{ active.location_label || active.place_name }} · {{ currentPerson }}</p><p v-if="active.explanation" class="explanation">{{ active.explanation }}</p><p v-if="single" class="certainty">{{ certainty[active.certainty] || '原始记录' }}</p>
      <p class="snapshot-score">线索快照评分 {{ fixed(single?chainData?.chain.total_score:active.total_score) }} / 100 · 底图颜色为对应时段的区域指数</p>
      <details><summary>来源与快照</summary><p>{{ active.source_table || (single?'信息节点':'consume_record') }} · {{ active.consume_id || active.track_id || active.order_id || active.score_id || '无位置来源' }}</p><p class="mono">{{ currentClue }}</p><p>快照截至 {{ single ? chainData?.chain.snapshot_at : active.snapshot_at }}</p><p v-if="active.source_record" class="source-copy">{{ JSON.stringify(active.source_record) }}</p></details>
      <div class="replay-detail-links"><button v-if="!single" class="plain" @click="openChain">展开此事件链 →</button><router-link v-if="currentClue" :to="{name:'clue-detail',params:{clueId:currentClue}}">线索详情 →</router-link><router-link :to="{name:'evidence',query:{scope:'person',person_id:currentPerson}}">证据浏览 →</router-link></div>
      <details v-if="single && chainData?.feedbacks.length"><summary>人工核查记录（不作为地图落点）</summary><p v-for="f in chainData.feedbacks" :key="f.feedback_id">{{ f.check_time }} · {{ f.check_remark }}</p></details>
    </template><p v-else>{{ loading?'正在读取回放…':'暂无可回放事件' }}</p>
  </section>
  <section class="replay-player" aria-label="线索回放播放器">
    <div class="player-controls"><el-button :icon="playing?VideoPause:VideoPlay" type="primary" :disabled="loading||events.length<2" @click="toggle">{{ playing?'暂停':'播放' }}</el-button><el-button :icon="DArrowLeft" aria-label="从头回放" :disabled="!events.length" @click="seek(0)" /><el-button :icon="ArrowLeft" aria-label="上一事件" :disabled="index<=0" @click="seek(index-1)" /><el-button :icon="ArrowRight" aria-label="下一事件" :disabled="index>=events.length-1" @click="seek(index+1)" /><el-select v-model="speed" aria-label="回放速度"><el-option v-for="s in [.5,1,2,4]" :key="s" :label="`${s}×`" :value="s" /></el-select><el-checkbox v-model="loop">循环</el-checkbox><el-checkbox v-model="follow">跟随</el-checkbox><el-checkbox v-model="reduced" @change="redraw">减少动画</el-checkbox></div>
    <div class="replay-progress"><el-slider :model-value="index" :min="0" :max="Math.max(1,events.length-1)" :step="1" :disabled="events.length<2" :format-tooltip="i=>events[i]?.event_at || ''" aria-label="线索事件进度" @update:model-value="seek" /><span>{{ events.length?`${index+1} / ${events.length}`:'0 / 0' }}</span></div>
    <div class="event-strip"><button v-for="(e,i) in events" :key="e.event_id || e.chain_id" :class="{current:i===index,past:i<index}" :aria-label="`跳到事件 ${i+1} ${e.title || e.area_name} ${e.event_at}`" @click="seek(i)"><span>{{ e.event_at.slice(11,16) }}</span><small>{{ e.title || e.area_name }}</small></button></div>
    <p>北京时间 · 每步约 {{ (2/speed).toFixed(1) }} 秒为演示节奏 · 区域落点与跳跃弧线不表示真实行驶路线</p>
  </section>
</template>

<script setup>
import {computed,nextTick,onBeforeUnmount,ref,watch} from 'vue'
import {ArrowLeft,ArrowRight,DArrowLeft,VideoPause,VideoPlay} from '@element-plus/icons-vue'
import {api} from '@/api'
import {allPages} from '@/utils/dashboard'
import {chronological} from '@/utils/clue-replay'
import {fixed} from '@/utils/format'
const props=defineProps({areas:{type:Array,required:true},initialDate:{type:String,default:''},showLinks:{type:Boolean,default:true}})
const emit=defineEmits(['frame','land','follow'])
const day=ref(''),area=ref(''),person=ref(''),rows=ref([]),loading=ref(false),error=ref(''),single=ref(false),chosen=ref(null),chainData=ref(null),index=ref(0),playing=ref(false),speed=ref(1),loop=ref(false),follow=ref(false),listOpen=ref(window.innerWidth>1200)
const media=window.matchMedia('(prefers-reduced-motion: reduce)'),reduced=ref(media.matches)
const events=computed(()=>single.value ? chronological(chainData.value?.nodes || []) : rows.value)
const active=computed(()=>events.value[index.value])
const currentClue=computed(()=>single.value?chainData.value?.chain.clue_id:active.value?.clue_id)
const currentPerson=computed(()=>single.value?chainData.value?.chain.person_id:active.value?.person_id)
const certainty={record:'原始记录',association:'关联推断 · 待核实',confirmed:'独立观察记录',counterexample:'安全出行反例',missing:'证据缺口'}
const areaName=id=>props.areas.find(a=>a.area_id===id)?.area_name || id
let requestId=0,frame=0,last=0,elapsed=0,target=null,landed=false,disposed=false
function pause(){playing.value=false;cancelAnimationFrame(frame);frame=0;last=0}
function send(i,progress){emit('frame',{events:events.value,index:reduced.value&&progress<1?index.value:i,progress:reduced.value?1:progress,chain:single.value,showLinks:props.showLinks})}
function land(i){const e=events.value[i];if(e){emit('land',e);if(follow.value&&e.area_id)emit('follow',e.area_id)}}
function seek(i){pause();target=null;elapsed=0;index.value=Math.max(0,Math.min(events.value.length-1,i));send(index.value,1);land(index.value);nextTick(scrollCurrent)}
function redraw(){send(target??index.value,target===null?1:Math.min(1,elapsed/2000))}
function scrollCurrent(){const strip=document.querySelector('.event-strip'),button=strip?.querySelector('.current');if(strip&&button){const x=button.offsetLeft-strip.offsetLeft;if(x<strip.scrollLeft||x+button.offsetWidth>strip.scrollLeft+strip.clientWidth)strip.scrollLeft=Math.max(0,x-strip.clientWidth/2)}}
function tick(time){
  if(!playing.value||disposed)return
  if(!last)last=time
  if(target===null){target=index.value+1;elapsed=0;landed=false}
  elapsed+=Math.min(100,time-last)*speed.value;last=time
  const p=Math.min(1,elapsed/2000);send(target,p)
  if(!landed&&(reduced.value?p>=1:p>=.76)){landed=true;index.value=target;land(index.value);nextTick(scrollCurrent)}
  if(p>=1){target=null;elapsed=0;if(index.value>=events.value.length-1){if(loop.value){index.value=0;send(0,1);land(0)}else{pause();return}}}
  frame=requestAnimationFrame(tick)
}
function toggle(){if(playing.value){pause();return}if(events.value.length<2)return;if(index.value>=events.value.length-1&&target===null)seek(0);playing.value=true;last=0;frame=requestAnimationFrame(tick)}
async function reload(){
  pause();const id=++requestId;loading.value=true;error.value='';rows.value=[];chainData.value=null;chosen.value=null;single.value=false;index.value=0;target=null;emit('frame',null)
  try{
    if(!day.value)return
    const end=new Date(day.value+'T12:00:00+08:00');end.setUTCDate(end.getUTCDate()+1)
    const params={from:day.value+' 00:00:00',to:end.toISOString().slice(0,10)+' 00:00:00',area_id:area.value,person_id:person.value.trim()}
    const all=await allPages(api.mapReplayEvents,params)
    if(id!==requestId||disposed)return
    rows.value=chronological(all);chosen.value=rows.value[0]||null;seek(0)
  }catch(e){if(id===requestId)error.value=e.message}finally{if(id===requestId)loading.value=false}
}
async function openChain(){
  pause();chosen.value=single.value?chosen.value:active.value
  if(!chosen.value)return
  const id=++requestId;loading.value=true;error.value='';chainData.value=null;single.value=true;emit('frame',null)
  try{const data=await api.mapReplayChain(chosen.value.chain_id);if(id!==requestId||disposed)return;chainData.value=data;seek(0)}catch(e){if(id===requestId)error.value=e.message}finally{if(id===requestId)loading.value=false}
}
function chooseEvent(e,i){pause();chosen.value=e;if(single.value)openChain();else seek(i)}
function setScope(value){if(value){if(!single.value)openChain()}else{pause();++requestId;loading.value=false;single.value=false;const i=rows.value.findIndex(e=>e.chain_id===chosen.value?.chain_id);seek(Math.max(0,i))}}
watch(()=>props.initialDate,value=>{if(!day.value&&value){day.value=value.slice(0,10);reload()}},{immediate:true})
watch(()=>props.showLinks,redraw)
function mediaChange(e){reduced.value=e.matches;redraw()}
function visibilityChange(){if(document.hidden)pause()}
media.addEventListener('change',mediaChange);document.addEventListener('visibilitychange',visibilityChange)
onBeforeUnmount(()=>{disposed=true;requestId++;pause();emit('frame',null);media.removeEventListener('change',mediaChange);document.removeEventListener('visibilitychange',visibilityChange)})
defineExpose({pause})
</script>

<style scoped>
.replay-filter,.replay-events,.replay-detail,.replay-player{position:absolute;background:#fff;border-radius:14px;padding:18px;box-shadow:0 4px 20px #20282e10}.replay-filter{top:76px;left:16px;width:380px}.replay-filter-head,.replay-panel-heading{display:flex;align-items:center;justify-content:space-between;gap:10px}.replay-filter h2{font-size:23px;font-weight:500;margin:0 0 12px}.replay-filter-head>span,.replay-panel-heading>span{font-size:11px;color:var(--text-muted);white-space:nowrap}.replay-filters{display:flex;gap:8px;margin-bottom:8px}.replay-filters :deep(.el-date-editor),.replay-filters .el-select{width:calc(50% - 4px)}.replay-scope{display:flex;gap:4px;margin-top:12px}.replay-scope button{border:0;background:#f0f2ef;padding:7px 12px;border-radius:6px;color:var(--text-secondary);font:inherit;font-size:12px;cursor:pointer}.replay-scope button[aria-pressed=true]{background:var(--accent-soft);color:var(--accent-ink)}.replay-scope button:disabled{opacity:.5;cursor:default}.replay-filter p,.replay-events>p,.replay-detail p{font-size:12px;line-height:1.7;color:var(--text-secondary);margin:8px 0 0}.plain{border:0;background:transparent;font:inherit;color:var(--accent-ink);cursor:pointer;padding:0}.replay-events{top:76px;right:76px;width:310px;max-height:calc(100% - 290px);display:flex;flex-direction:column}.replay-panel-heading h3{font-size:15px;font-weight:500;margin:0}.replay-list{overflow:auto;margin-top:12px}.replay-event-row{display:grid;grid-template-columns:42px 1fr auto;gap:9px;align-items:center;width:100%;border:0;border-bottom:1px solid var(--card-border);border-radius:6px;background:transparent;padding:13px 4px;text-align:left;color:var(--text-primary);cursor:pointer;font:inherit;font-size:12px}.replay-event-row.selected{background:var(--accent-soft)}.replay-event-row strong{display:block;font-weight:500}.replay-event-row small{display:block;color:var(--text-muted);font-size:10px;line-height:1.7;margin-top:4px}.event-score{text-align:right;font-family:var(--font-data);font-size:18px}.event-score small{font-family:var(--font-ui)}.event-time{font-family:var(--font-mono);font-size:11px}.replay-detail{bottom:225px;left:16px;width:380px;max-height:330px;overflow:auto}.replay-detail .detail-time{font-family:var(--font-mono);font-size:12px;color:var(--text-muted)}.replay-detail .detail-location{font-size:21px;font-weight:500;color:var(--text-primary)}.replay-detail .explanation{line-height:1.8}.certainty{color:var(--accent-ink)!important}.replay-detail details{margin-top:10px;font-size:11px;line-height:1.7}.replay-detail summary{cursor:pointer;color:var(--text-muted)}.source-copy{overflow-wrap:anywhere}.replay-detail-links{display:flex;gap:12px;flex-wrap:wrap;font-size:12px;margin-top:12px}.replay-player{bottom:16px;left:16px;right:16px;padding:14px 18px}.player-controls{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.player-controls .el-button+.el-button{margin:0}.player-controls .el-select{width:72px}.player-controls .el-checkbox{margin-right:8px}.replay-progress{display:flex;align-items:center;gap:14px}.replay-progress .el-slider{flex:1}.replay-progress>span{font-family:var(--font-mono);font-size:11px;white-space:nowrap}.event-strip{display:flex;gap:6px;overflow:auto;max-width:100%;padding-bottom:4px;scrollbar-width:thin}.event-strip button{flex:0 0 96px;border:0;border-radius:5px;background:#f3f5f1;padding:6px 8px;color:var(--text-muted);font:inherit;text-align:left;cursor:pointer}.event-strip .past{background:#ecf0f5}.event-strip .current{background:var(--accent-soft);color:var(--accent-ink)}.event-strip span{display:block;font:11px var(--font-mono)}.event-strip small{display:block;font-size:11px;margin-top:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.replay-player>p{font-size:10px;color:var(--text-muted);margin:7px 0 0;line-height:1.6}.collapse-list{display:block}
@media(max-width:1200px){.replay-events{top:380px;right:16px;max-height:210px;width:280px}.collapse-list{display:block}.replay-detail{bottom:245px;max-height:230px}.replay-filter{width:min(380px,calc(100% - 96px))}}
@media(max-width:600px){.replay-filter{top:76px;left:12px;width:calc(100% - 78px);padding:12px}.replay-filter h2{font-size:19px}.replay-filter-head>span{display:none}.replay-filter p{font-size:10px}.replay-events{top:340px;right:12px;width:calc(100% - 24px);max-height:180px;padding:12px}.replay-detail{left:12px;right:12px;width:auto;bottom:285px;max-height:240px;padding:12px}.replay-player{left:12px;right:12px;padding:12px;bottom:12px}.player-controls{gap:5px}.player-controls .el-checkbox{margin-right:5px;height:24px;font-size:11px}.player-controls .el-button{padding:6px 9px}.event-strip button{flex-basis:86px}.replay-filter-head{gap:4px}.replay-filters{flex-wrap:wrap}.replay-filters :deep(.el-date-editor){width:140px}.replay-filters .el-select{width:100%}}
</style>
