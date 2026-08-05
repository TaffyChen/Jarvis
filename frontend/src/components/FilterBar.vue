<template>
  <div class="filter-bar">
    <input
      class="search-input"
      :value="search"
      placeholder="搜索名称/代码/板块..."
      @input="$emit('update:search', $event.target.value)"
    >
    <div class="tabs">
      <button
        v-for="t in tabs"
        :key="t.id"
        :class="['tab', { active: filter === t.id }]"
        @click="$emit('update:filter', t.id)"
      >
        {{ t.label }}
        <span class="tab-count">{{ counts[t.id] ?? 0 }}</span>
      </button>
    </div>
    <div class="sector-row">
      <button
        :class="['sector-tag', { active: sector === 'all' }]"
        @click="$emit('update:sector', 'all')"
      >全部</button>
      <button
        v-for="s in sectors"
        :key="s.name"
        :class="['sector-tag', { active: sector === s.name }]"
        @click="$emit('update:sector', s.name)"
      >{{ s.name }} ({{ s.count }})</button>
    </div>
  </div>
</template>

<script setup>
defineProps({
  search: String,
  filter: String,
  sector: String,
  counts: { type: Object, default: () => ({}) },
  sectors: { type: Array, default: () => [] },
})
defineEmits(['update:search', 'update:filter', 'update:sector'])

const tabs = [
  { id: 'all', label: '全部' },
  { id: 'buy', label: '可买入' },
  { id: 'watch', label: '观察' },
  { id: 'nochase', label: '不追' },
  { id: 'hold', label: '持仓' },
  { id: 'exclude', label: '排除' },
]
</script>
