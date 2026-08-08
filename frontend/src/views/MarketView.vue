<template>
  <div class="market-view">
    <MarketOverview
      page-mode
      :indices="dash.indices"
      :market-turnover="dash.marketTurnover"
      :market-breadth="dash.marketBreadth"
      :overseas="dash.overseas"
      :conditions="dash.conditions"
      :lamps="dash.lamps"
      :position-rec="dash.positionRec"
      :sentiment="dash.sentimentBrief"
      :sentiment-history="dash.sentimentHistory"
      :advice="dash.dailyAdvice"
      :sector-flow="dash.sectorFlow"
      @toggle-lever="$emit('toggle-lever')"
      @open-sector="$emit('open-sector')"
    />
    <div class="market-bottom">
      <MainRiseBar :main-rise="dash.mainRise" @toggle-ice="$emit('toggle-ice')" />
      <button type="button" class="btn btn-primary market-stocks-btn" @click="$emit('open-stocks')">
        自选
      </button>
    </div>
  </div>
</template>

<script setup>
import { useDashboardStore } from '../stores/dashboard'
import MarketOverview from '../components/MarketOverview.vue'
import MainRiseBar from '../components/MainRiseBar.vue'

defineEmits(['toggle-lever', 'toggle-ice', 'open-sector', 'open-stocks'])
const dash = useDashboardStore()
</script>

<style scoped>
.market-view {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-height: 0;
}
.market-bottom {
  display: flex;
  align-items: stretch;
  gap: 8px;
}
.market-bottom :deep(.mainrise-bar) {
  flex: 1;
  min-width: 0;
  margin-bottom: 0;
}
.market-stocks-btn {
  flex-shrink: 0;
  align-self: center;
  white-space: nowrap;
}
</style>
