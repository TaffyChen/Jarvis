<template>
  <DecisionCapsule
    :position-rec="dash.positionRec"
    :sentiment="dash.sentimentBrief"
    :advice="dash.dailyAdvice"
    @open-market="$emit('open-market')"
  />

  <FilterBar
    v-model:search="dash.search"
    v-model:filter="dash.filter"
    v-model:sector="dash.sector"
    :counts="dash.tabCounts"
    :sectors="dash.sectors"
    :stock-layout="stockLayout"
    :visible-count="dash.cards.length"
    :total-count="dash.items.length"
    :hold-summary="holdSummary.count ? holdSummary : null"
    @layout="(v) => $emit('layout', v)"
  />

  <template v-if="dash.cards.length">
    <div v-if="stockLayout === 'card'" class="stock-grid">
      <StockCard
        v-for="(c, idx) in dash.cards"
        :key="c.code"
        :card="c"
        :idx="idx"
        @review="(code, ok) => $emit('review', code, ok)"
        @edit-position="(card) => $emit('edit-position', card)"
        @journal="(a) => $emit('journal', a)"
        @remove="(card) => $emit('remove', card)"
      />
    </div>
    <StockList
      v-else
      :cards="dash.cards"
      @review="(code, ok) => $emit('review', code, ok)"
      @edit-position="(card) => $emit('edit-position', card)"
      @journal="(a) => $emit('journal', a)"
      @remove="(card) => $emit('remove', card)"
    />
  </template>
  <div v-else class="empty">没有匹配的标的。调整筛选，或点「添加标的」。</div>
</template>

<script setup>
import { computed } from 'vue'
import { useDashboardStore } from '../stores/dashboard'
import FilterBar from '../components/FilterBar.vue'
import StockCard from '../components/StockCard.vue'
import StockList from '../components/StockList.vue'
import DecisionCapsule from '../components/DecisionCapsule.vue'

defineProps({
  stockLayout: { type: String, default: 'card' },
})
defineEmits(['layout', 'review', 'edit-position', 'journal', 'remove', 'open-market'])

const dash = useDashboardStore()

const holdSummary = computed(() => {
  let count = 0
  let cost = 0
  let marketValue = 0
  for (const [code, pos] of Object.entries(dash.positions || {})) {
    const shares = Number(pos.shares) || 0
    const buy = Number(pos.buyPrice) || 0
    if (!(shares > 0)) continue
    count += 1
    cost += buy * shares
    const price = Number(dash.quotes[code]?.price) || buy
    marketValue += price * shares
  }
  const pnl = marketValue - cost
  const pnlPct = cost > 0 ? (pnl / cost) * 100 : 0
  return { count, cost, marketValue, pnl, pnlPct }
})
</script>
