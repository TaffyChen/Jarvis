<template>
  <MainRiseBar :main-rise="dash.mainRise" @toggle-ice="$emit('toggle-ice')" />

  <FilterBar
    v-model:search="dash.search"
    v-model:filter="dash.filter"
    v-model:sector="dash.sector"
    :counts="dash.tabCounts"
    :sectors="dash.sectors"
  />

  <div class="section-head">
    <div class="section-head-left">
      <h2>{{ stockLayout === 'list' ? '标的列表' : '标的卡片' }}</h2>
      <span class="muted">共 {{ dash.cards.length }} / {{ dash.items.length }} 只</span>
    </div>
    <div class="layout-toggle" role="group" aria-label="标的展示形式">
      <button type="button" :class="{ active: stockLayout === 'card' }" @click="$emit('layout', 'card')">卡片</button>
      <button type="button" :class="{ active: stockLayout === 'list' }" @click="$emit('layout', 'list')">列表</button>
    </div>
  </div>

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
      />
    </div>
    <StockList
      v-else
      :cards="dash.cards"
      @review="(code, ok) => $emit('review', code, ok)"
      @edit-position="(card) => $emit('edit-position', card)"
      @journal="(a) => $emit('journal', a)"
    />
  </template>
  <div v-else class="empty">没有匹配的标的。调整筛选，或点「添加标的」。</div>
</template>

<script setup>
import { useDashboardStore } from '../stores/dashboard'
import FilterBar from '../components/FilterBar.vue'
import StockCard from '../components/StockCard.vue'
import StockList from '../components/StockList.vue'
import MainRiseBar from '../components/MainRiseBar.vue'

defineProps({
  stockLayout: { type: String, default: 'card' },
})
defineEmits(['toggle-ice', 'layout', 'review', 'edit-position', 'journal'])

const dash = useDashboardStore()
</script>
