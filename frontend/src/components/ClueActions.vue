<template>
  <div v-if="canAct" class="clue-actions">
    <template v-if="status===0"><el-button type="primary" :loading="acting" @click="$emit('start')">开始核查</el-button><el-button @click="$emit('feedback',{preset:2,lock:true,title:'直接排除'})">直接排除</el-button></template>
    <template v-else-if="status===1"><el-button type="danger" @click="$emit('feedback',{preset:1,lock:false,title:'确认属实'})">确认属实</el-button><el-button @click="$emit('feedback',{preset:2,lock:false,title:'排除'})">排除</el-button></template>
  </div>
</template>
<script setup>
defineProps({status:Number,canAct:Boolean,acting:Boolean})
defineEmits(['start','feedback'])
</script>
<style scoped>
.clue-actions { display:flex; flex-wrap:wrap; gap:10px; }.clue-actions .el-button { margin:0; }
</style>
