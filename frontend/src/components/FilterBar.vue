<template>
  <div class="filter-bar">
    <div class="search-wrap">
      <input
        class="search-input"
        :value="search"
        placeholder="搜索名称/代码/板块/首字母(hdgf、bdt)..."
        @input="onSearchInput"
      >
      <button
        v-if="search"
        type="button"
        class="search-clear"
        title="清空"
        aria-label="清空搜索"
        @click="clearSearch"
      >×</button>
    </div>
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
        :class="['sector-tag', { active: sector === 'all' && !searchSectorHits.length }]"
        @click="pickSector('all')"
      >全部</button>
      <button
        v-for="s in sectors"
        :key="s.name"
        :ref="(el) => setSectorRef(s.name, el)"
        :class="['sector-tag', {
          active: sector === s.name || searchSectorHits.includes(s.name),
        }]"
        @click="pickSector(s.name)"
      >{{ s.name }} ({{ s.count }})</button>
    </div>
    <div class="filter-meta">
      <span class="filter-count muted">{{ visibleCount }} / {{ totalCount }}</span>
      <div class="layout-toggle" role="group" aria-label="标的展示形式">
        <button type="button" :class="{ active: stockLayout === 'card' }" @click="$emit('layout', 'card')">卡片</button>
        <button type="button" :class="{ active: stockLayout === 'list' }" @click="$emit('layout', 'list')">列表</button>
      </div>
    </div>
    <div v-if="holdSummary?.count" class="hold-summary-inline">
      <span class="hold-summary-label">持仓 {{ holdSummary.count }}</span>
      <span :class="holdSummary.pnl >= 0 ? 'up' : 'down'">
        {{ holdSummary.pnl >= 0 ? '+' : '' }}{{ Math.round(holdSummary.pnl).toLocaleString('zh-CN') }}
        （{{ holdSummary.pnlPct >= 0 ? '+' : '' }}{{ holdSummary.pnlPct.toFixed(1) }}%）
      </span>
      <span class="muted">市值 {{ Math.round(holdSummary.marketValue).toLocaleString('zh-CN') }}</span>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import { sectorTagMatches } from '../utils/match.js'

const props = defineProps({
  search: String,
  filter: String,
  sector: String,
  counts: { type: Object, default: () => ({}) },
  sectors: { type: Array, default: () => [] },
  stockLayout: { type: String, default: 'card' },
  visibleCount: { type: Number, default: 0 },
  totalCount: { type: Number, default: 0 },
  holdSummary: { type: Object, default: null },
})
const emit = defineEmits(['update:search', 'update:filter', 'update:sector', 'layout'])

const tabs = [
  { id: 'all', label: '全部' },
  { id: 'buy', label: '可买入' },
  { id: 'watch', label: '观察' },
  { id: 'nochase', label: '不追' },
  { id: 'hold', label: '持仓' },
  { id: 'exclude', label: '排除' },
]

const sectorEls = ref({})

function setSectorRef(name, el) {
  if (el) sectorEls.value[name] = el
  else delete sectorEls.value[name]
}

const searchSectorHits = computed(() => {
  const q = String(props.search || '').trim()
  if (!q) return []
  return (props.sectors || [])
    .map((s) => s.name)
    .filter((name) => sectorTagMatches(name, q))
})

function onSearchInput(e) {
  emit('update:search', e.target.value)
}

function clearSearch() {
  emit('update:search', '')
  emit('update:sector', 'all')
}

function pickSector(name) {
  emit('update:sector', name)
  // 点板块 chip 时清掉搜索，避免「chip + 搜索」两套条件打架
  if (props.search) emit('update:search', '')
}

watch(searchSectorHits, async (hits) => {
  if (!hits.length) return
  await nextTick()
  const el = sectorEls.value[hits[0]]
  el?.scrollIntoView?.({ behavior: 'smooth', inline: 'center', block: 'nearest' })
})
</script>
