<template>
  <div ref="el" class="chart" :style="{ height }" />
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import { chartTheme } from '@/styles/chart-theme'
echarts.registerTheme('risk-workbench', chartTheme)

const props = defineProps({
  option: { type: Object, required: true },
  height: { type: String, default: '280px' },
})
const emit = defineEmits(['click'])

const el = ref(null)
let chart = null
let ro = null

onMounted(() => {
  chart = echarts.init(el.value, 'risk-workbench')
  chart.setOption(props.option)
  chart.on('click', (p) => emit('click', p))
  ro = new ResizeObserver(() => chart?.resize())
  ro.observe(el.value)
})

watch(() => props.option, (opt) => chart?.setOption(opt, true), { deep: true })

onBeforeUnmount(() => {
  ro?.disconnect()
  chart?.dispose()
})
</script>

<style scoped>
.chart { width: 100%; }
</style>
