<template>
  <div ref="root" class="street-map" tabindex="0" aria-label="区域风险地图，方向键平移，加减键缩放" @keydown="onKey">
    <div v-show="!fallback" ref="host" class="scene-host" />
    <svg v-if="fallback" class="flat-map" :viewBox="flatViewBox" aria-label="二维街区风险地图" @pointerdown="flatDown" @pointermove="flatMove" @pointerup="flatUp" @pointercancel="flatUp" @wheel.prevent="flatWheel">
      <defs><radialGradient id="street-heat"><stop offset="0" stop-color="currentColor" stop-opacity=".7" /><stop offset="1" stop-color="currentColor" stop-opacity="0" /></radialGradient></defs>
      <rect x="-1000" y="-1000" width="2000" height="2000" fill="#e9ede7" />
      <g fill="#fafbf7" stroke="#cad3c7" stroke-width=".3"><rect v-for="(r,i) in layout.roads" :key="i" :x="r.x-r.w/2" :y="r.z-r.d/2" :width="r.w" :height="r.d" /></g>
      <g v-if="showBuildings" fill="#c3cec1"><rect v-for="(b,i) in layout.buildings" :key="i" :x="b.x-b.w/2" :y="b.z-b.d/2" :width="b.w" :height="b.d" /></g>
      <g v-if="showLinks" fill="none" stroke-width=".6"><path v-for="e in layout.edges" :key="e.id" :d="flatPath(e)" :stroke="edgeActive(e) ? '#345fc5' : '#80949c'" :opacity="edgeActive(e) ? 1 : .5" @pointerenter="edgeHover(e,$event)" @pointerleave="clearHover" /></g>
      <g v-for="n in layout.nodes" :key="n.area_id" :transform="`translate(${n.x} ${n.z})`" :style="{color:riskColor(risk[n.area_id]?.total_score)}" @pointerenter="nodeHover(n.area_id,$event)" @pointerleave="clearHover">
        <circle v-if="risk[n.area_id]" r="11" fill="url(#street-heat)" />
        <circle v-if="selected===n.area_id" r="3.6" fill="none" stroke="#345fc5" stroke-width=".6" />
        <circle r="2.3" fill="currentColor" stroke="#79897a" stroke-width=".3" />
      </g>
    </svg>
    <div class="map-labels">
      <button v-for="n in labels" :key="n.area_id" class="map-label" :class="{'is-selected':selected===n.area_id}" :style="{left:`${n.left}px`,top:`${n.top}px`}" :aria-pressed="selected===n.area_id" :aria-label="`${n.area_name}，${risk[n.area_id] ? `${fixed(risk[n.area_id].total_score)}分` : '当夜无研判数据'}`" @click="emit('select',n.area_id)" @pointerenter="nodeHover(n.area_id,$event)" @pointerleave="clearHover" @focus="nodeHover(n.area_id,$event)" @blur="clearHover">{{ n.area_name }}<b v-if="selected===n.area_id && risk[n.area_id]">{{ fixed(risk[n.area_id].total_score) }}</b></button>
    </div>
    <div v-if="hover" class="map-point-tip" role="tooltip" :style="tipStyle">
      <template v-if="hover.kind==='node'"><strong>{{ hoverNode?.area_name }}</strong><template v-if="hoverRisk"><span>{{ hoverRisk.risk_level_name }}风险 · {{ fixed(hoverRisk.total_score) }} 分</span><span>样本 {{ hoverRisk.sample_size }} · 命中 {{ hoverRisk.hit_cnt }} 项</span></template><span v-else>当夜无研判数据</span></template>
      <template v-else><strong>{{ hoverEdgeNames }}</strong><span>空间邻近示意 · 无方向连接</span></template>
    </div>
    <div class="scene-status"><span>{{ fallback ? '二维街区' : '三维街区' }}</span><span>街道与链路为教学示意</span></div>
    <div v-if="fallback" class="fallback-note" :style="{top:size.w>1128?'16px':`${insets.top-14}px`}" role="status">{{ fallbackReason }}<button @click="start">重试三维</button></div>
    <div v-if="starting" class="scene-loading" role="status">正在加载三维街区…</div>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { streetLayout, riskColor, edgeHeight } from '@/utils/street-map'
import { fixed } from '@/utils/format'
const props=defineProps({areas:{type:Array,required:true},risk:{type:Object,required:true},selected:{type:String,default:''},showBuildings:{type:Boolean,default:true},showLinks:{type:Boolean,default:true},mode:{type:String,default:'inclined'},insets:{type:Object,default:()=>({})}})
const emit=defineEmits(['select','mode'])
const root=ref(null),host=ref(null),projected=ref([]),fallback=ref(false),starting=ref(true),hover=ref(null),tipPosition=ref({x:0,y:0})
const fallbackReason=ref('当前设备暂无法显示三维，已保留二维地图与全部业务操作。')
const layout=computed(()=>streetLayout(props.areas))
const size=ref({w:1000,h:700}),flatCamera=ref({x:0,z:0,zoom:1})
let scene=null,observer=null,disposed=false,generation=0
const flatDimensions=computed(()=>{
  const {w,h}=size.value,{left=24,right=24,top=180,bottom=260}=props.insets
  const fullH=Math.max(202*h/Math.max(180,h-top-bottom),202*h/Math.max(180,w-left-right))/flatCamera.value.zoom
  const fullW=fullH*w/h
  return {w:fullW,h:fullH,x:-fullW/2+flatCamera.value.x-(left-right)/w*fullW/2,z:-fullH/2+flatCamera.value.z-(top-bottom)/h*fullH/2}
})
const flatViewBox=computed(()=>{const d=flatDimensions.value;return `${d.x} ${d.z} ${d.w} ${d.h}`})
const positions=computed(()=>fallback.value ? layout.value.nodes.map((n)=>{const d=flatDimensions.value;return {...n,left:(n.x-d.x)/d.w*size.value.w,top:(n.z-d.z)/d.h*size.value.h,visible:true}}) : projected.value)
// Fixed ID order keeps label placement stable when night scores change.
const labels=computed(()=>{
  const {w,h}=size.value,placed=[]
  const candidates=positions.value.slice().sort((a,b)=>Number(b.area_id===props.selected)-Number(a.area_id===props.selected)||a.area_id.localeCompare(b.area_id))
  for(const n of candidates){
    const labelW=n.area_name.length*12+20+(n.area_id===props.selected ? 40 : 0)
    if(!n.visible)continue
    for(const offset of [12,-33,35]){
      const box={left:n.left-labelW/2,right:n.left+labelW/2,top:n.top+offset,bottom:n.top+offset+25}
      if(box.left<5 || box.right>w-5 || box.top<5 || box.bottom>h-8)continue
      if(placed.some((p)=>box.left<p.box.right+4 && box.right>p.box.left-4 && box.top<p.box.bottom+3 && box.bottom>p.box.top-3))continue
      placed.push({...n,top:n.top+offset,box});break
    }
  }
  return placed
})
const hoverNode=computed(()=>layout.value.nodes.find((n)=>n.area_id===hover.value?.id))
const hoverRisk=computed(()=>props.risk[hover.value?.id])
const hoverEdgeNames=computed(()=>{const e=layout.value.edges.find((e)=>e.id===hover.value?.id);return e ? [e.a,e.b].map((id)=>layout.value.nodes.find((n)=>n.area_id===id)?.area_name).join(' — ') : ''})
const tipStyle=computed(()=>({left:`${Math.max(8,Math.min(size.value.w-260,tipPosition.value.x+16))}px`,top:`${Math.max(8,Math.min(size.value.h-112,tipPosition.value.y-98))}px`}))
function receiveHover(value,event){
  hover.value=value
  if(!value)return
  const rect=root.value.getBoundingClientRect()
  if(event?.clientX != null && event.type!=='focus')tipPosition.value={x:event.clientX-rect.left,y:event.clientY-rect.top}
  else {const p=positions.value.find((n)=>n.area_id===value.id);tipPosition.value={x:p?.left||rect.width/2,y:p?.top||rect.height/2}}
}
function nodeHover(id,event){if(scene)scene.hover(id,event);else receiveHover({kind:'node',id},event)}
function edgeHover(e,event){receiveHover({kind:'edge',id:e.id},event)}
function clearHover(){if(scene)scene.hover(null);else hover.value=null}
function edgeActive(e){return e.id===hover.value?.id || e.a===props.selected || e.b===props.selected}
function flatPath(e){const a=layout.value.nodes.find((n)=>n.area_id===e.a),b=layout.value.nodes.find((n)=>n.area_id===e.b);return `M ${a.x} ${a.z} Q ${(a.x+b.x)/2} ${(a.z+b.z)/2-edgeHeight(e.distance)*.45} ${b.x} ${b.z}`}
function updateScene(){scene?.update({risk:props.risk,selected:props.selected,buildings:props.showBuildings,links:props.showLinks,mode:props.mode,insets:props.insets})}
function useFallback(){generation++;scene?.dispose();scene=null;fallback.value=true;starting.value=false;hover.value=null;emit('mode',true)}
function toggleFlat(){if(fallback.value)start();else {fallbackReason.value='已切换二维模式，支持拖动、双指缩放和区域选择。';useFallback()}}
async function start(){
  const current=++generation
  scene?.dispose();scene=null;fallback.value=false;starting.value=true;hover.value=null
  fallbackReason.value='当前设备暂无法显示三维，已保留二维地图与全部业务操作。'
  await nextTick()
  try {
    const {createStreetScene}=await import('./street-scene')
    if(disposed||current!==generation)return
    scene=createStreetScene(host.value,layout.value,{onProject:(rows)=>{projected.value=rows},onHover:receiveHover,onSelect:(id)=>emit('select',id),onFailure:useFallback})
    updateScene();starting.value=false;emit('mode',false)
  }catch {if(!disposed&&current===generation)useFallback()}
}
function reset(){hover.value=null;flatCamera.value={x:0,z:0,zoom:1};scene?.reset()}
function zoom(factor){if(scene)scene.zoom(factor);else flatCamera.value={...flatCamera.value,zoom:Math.max(.6,Math.min(3.5,flatCamera.value.zoom*factor))}}
function focusArea(id){if(scene)scene.focus(id);else {const n=layout.value.nodes.find((n)=>n.area_id===id);if(n)flatCamera.value={...flatCamera.value,x:n.x*.45,z:n.z*.45}}}
function pan(x,z){if(scene)scene.pan(x,z);else flatCamera.value={...flatCamera.value,x:flatCamera.value.x+x,z:flatCamera.value.z+z}}
function onKey(e){
  if(e.target!==root.value)return
  const actions={ArrowLeft:()=>pan(-8,0),ArrowRight:()=>pan(8,0),ArrowUp:()=>pan(0,-8),ArrowDown:()=>pan(0,8),'+':()=>zoom(1.2),'=':()=>zoom(1.2),'-':()=>zoom(1/1.2),Home:reset}
  if(actions[e.key]){e.preventDefault();actions[e.key]()}
}
const pointers=new Map();let flatGesture=null
function flatDown(e){
  pointers.set(e.pointerId,{x:e.clientX,y:e.clientY});e.currentTarget.setPointerCapture(e.pointerId)
  flatGesture={camera:{...flatCamera.value},points:[...pointers.values()],moved:false,start:{x:e.clientX,y:e.clientY}}
  hover.value=null
}
function flatMove(e){
  if(!pointers.has(e.pointerId)||!flatGesture)return
  pointers.set(e.pointerId,{x:e.clientX,y:e.clientY});const points=[...pointers.values()],start=flatGesture.points
  if(points.length===2&&start.length===2){const ratio=Math.hypot(points[0].x-points[1].x,points[0].y-points[1].y)/Math.max(1,Math.hypot(start[0].x-start[1].x,start[0].y-start[1].y));flatCamera.value={...flatGesture.camera,zoom:Math.max(.6,Math.min(3.5,flatGesture.camera.zoom*ratio))};flatGesture.moved=true}
  else if(points.length===1&&start.length===1){const dx=points[0].x-start[0].x,dy=points[0].y-start[0].y,d=flatDimensions.value;flatCamera.value={...flatCamera.value,x:flatGesture.camera.x-dx*d.w/size.value.w,z:flatGesture.camera.z-dy*d.h/size.value.h};if(Math.hypot(dx,dy)>5)flatGesture.moved=true}
}
function flatUp(e){
  if(flatGesture&&!flatGesture.moved&&pointers.size===1&&e.type!=='pointercancel'){
    const rect=root.value.getBoundingClientRect(),p=positions.value.find((n)=>Math.hypot(n.left-(e.clientX-rect.left),n.top-(e.clientY-rect.top))<16)
    if(p)emit('select',p.area_id)
  }
  pointers.delete(e.pointerId);flatGesture=null
}
function flatWheel(e){zoom(e.deltaY<0?1.1:1/1.1)}
watch(()=>[props.risk,props.selected,props.showBuildings,props.showLinks,props.mode,props.insets],()=>{hover.value=null;updateScene()},{deep:true})
watch(layout,()=>{if(!fallback.value)start()})
onMounted(()=>{observer=new ResizeObserver(()=>{size.value={w:root.value.clientWidth,h:root.value.clientHeight}});observer.observe(root.value);start()})
onBeforeUnmount(()=>{disposed=true;generation++;observer?.disconnect();scene?.dispose()})
defineExpose({reset,zoom,focusArea,toggleFlat})
</script>

<style scoped>
.street-map,.scene-host,.flat-map,.map-labels{position:absolute;inset:0;width:100%;height:100%}.street-map{background:#e9ede7;outline-offset:-3px}.scene-host :deep(canvas){display:block;touch-action:none}.flat-map{touch-action:none;cursor:grab}.map-labels{pointer-events:none;overflow:hidden}.map-label{position:absolute;transform:translateX(-50%);pointer-events:auto;white-space:nowrap;background:#f8faf5e8;border:0;border-radius:4px;padding:3px 6px;color:#4c5b50;font:12px/1.5 var(--font-ui);cursor:pointer}.map-label:hover,.map-label.is-selected{background:#fff;color:#284da6;box-shadow:0 2px 6px #26382d16}.map-label b{margin-left:7px;font-family:var(--font-data);font-weight:500}.map-point-tip{position:absolute;z-index:5;pointer-events:none;display:flex;flex-direction:column;gap:5px;max-width:250px;background:#fff;padding:12px 16px;border-radius:10px;box-shadow:0 5px 20px #20282e1a;font-size:12px;line-height:1.6}.map-point-tip strong{font-size:13px;font-weight:500}.map-point-tip span{color:var(--text-secondary)}.scene-status{position:absolute;left:16px;bottom:115px;display:flex;gap:10px;pointer-events:none;color:#526254;font-size:11px;line-height:1.7}.scene-status span{background:#f8faf5e8;padding:2px 6px;border-radius:3px}.fallback-note{position:absolute;left:16px;top:205px;max-width:360px;padding:8px 12px;background:#fff;font-size:12px;line-height:1.8;box-shadow:0 3px 12px #20282e10;border-radius:8px}.fallback-note button{background:transparent;border:0;color:var(--accent-ink);cursor:pointer;padding:4px 8px;font:inherit}.scene-loading{position:absolute;left:50%;top:45%;transform:translate(-50%,-50%);background:#fff;padding:12px 18px;border-radius:10px;font-size:13px}
@media(max-width:600px){.map-label{font-size:11px;padding:2px 4px}.scene-status{left:12px;right:12px;bottom:115px;gap:6px;flex-wrap:wrap}.fallback-note{top:260px;left:12px;right:12px}.map-point-tip{max-width:240px}}
.scene-status{bottom:107px;font-size:10px;line-height:1.5}.fallback-note{left:420px;max-width:calc(100% - 800px)}
@media(max-width:1200px){.fallback-note{left:16px;right:76px;max-width:360px}}
</style>
