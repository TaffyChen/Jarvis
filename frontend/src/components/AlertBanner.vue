<template>
  <div v-if="alerts.length" :class="['alert-strip', danger ? 'danger' : 'warning']">
    <strong style="white-space:nowrap">{{ danger ? '持仓预警' : '持仓提醒' }} ({{ alerts.length }})</strong>
    <span v-for="(a, i) in alerts" :key="i" :class="['alert-chip', a.level]">
      {{ a.name }}：{{ a.msg }} → {{ a.action }}
      <button class="btn btn-sm btn-ghost" @click="$emit('journal', a)">记日记</button>
    </span>
  </div>
</template>

<script setup>
import { computed } from 'vue'
const props = defineProps({ alerts: { type: Array, default: () => [] } })
defineEmits(['journal'])
const danger = computed(() => props.alerts.some((a) => a.level === 'danger'))
</script>
